import json
import uuid
import requests
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import hashlib
import base64
from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from urllib.parse import urlparse
from urllib.parse import urlencode
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from app import app

# TODO: Set dynamically.
PSU_IP_ADDRESS = "212.178.101.162"

REDIRECT_URL = app.config["REDIRECT_URL"]
API_URL_PREFIX = "https://api.xs2a{}.bngbank.nl/api/v1/"
OAUTH_URL_PREFIX = "https://api.xs2a{}.bngbank.nl/authorise?response_type=code&"
ACCESS_TOKEN_URL = "https://api.xs2a{}.bngbank.nl/token"

if app.config["USE_SANDBOX"]:
    API_URL_PREFIX = API_URL_PREFIX.format("-sandbox")
    OAUTH_URL_PREFIX = OAUTH_URL_PREFIX.format("-sandbox")
    ACCESS_TOKEN_URL = ACCESS_TOKEN_URL.format("-sandbox")
    CLIENT_ID = "PSDNL-AUT-SANDBOX"
    TLS_CERTS = app.config["SANDBOX_CERTS"]["TLS"]
    SIGNING_CERTS = app.config["SANDBOX_CERTS"]["SIGNING"]
    KEYID_FDN = app.config["SANDBOX_KEYID_FDN"]
else:
    API_URL_PREFIX = API_URL_PREFIX.format("")
    OAUTH_URL_PREFIX = OAUTH_URL_PREFIX.format("")
    ACCESS_TOKEN_URL = ACCESS_TOKEN_URL.format("")
    CLIENT_ID = app.config["CLIENT_ID"]
    TLS_CERTS = SIGNING_CERTS = app.config["PRODUCTION_CERTS"]
    KEYID_FDN = app.config["PRODUCTION_KEYID_FDN"]


def get_cert_data(cert):
    with open(cert, "rb") as f:
        x = x509.load_pem_x509_certificate(f.read(), default_backend())
    # Why does this not start with two zeros as in get_signature?
    # See: 00E8B54055D929413F
    serial_number = '%x' % x.serial_number
    # Discrepancies:
    # '2.5.4.97=PSDNL-AUT-SANDBOX'                     ---> 'OID.2.5.4.97=PSDNL-AUT-SANDBOX'?
    # ST=South-Holland                                 ---> S=South-Holland
    # '1.2.840.113549.1.9.1=klantenservice@bngbank.nl' ---> E=klantenservice@bngbank.nl
    # 'CN=xs2a_sandbox_bngbank_client_signing'         ---> CA=CN=xs2a_sandbox_bngbank_client_signing
    issuer = str(x.issuer).replace("<Name(", "").replace(")>", "").split(",")
    return serial_number, issuer


def get_current_rfc_1123_date():
    now = datetime.now()
    stamp = mktime(now.timetuple())
    return format_date_time(stamp)


def get_digest(body):
    hash = hashlib.sha256()
    hash.update(body.encode("utf-8"))
    digest_in_bytes = hash.digest()
    digest_in_base64 = base64.b64encode(digest_in_bytes)
    return "SHA-256=" + digest_in_base64.decode("utf-8")


def get_signature(method, headers):
    signature_header_names = ["request-target", "Date", "Digest", "X-Request-ID"]
    headers = {k: v for k, v in headers.items() if k in signature_header_names}
    headers = {
        "(request-target)" if k == "request-target" else k.lower(): v
        for k, v in headers.items()
    }
    path = urlparse(headers["(request-target)"]).path
    tail = headers["(request-target)"].split(path)[-1]
    headers["(request-target)"] = method + " " + path + tail

    signing_string = "\n".join([k + ": " + v for k, v in headers.items()])
    signature_headers = " ".join(headers.keys())

    digest = SHA256.new()
    digest.update(bytes(signing_string, encoding="utf-8"))

    with open(SIGNING_CERTS[1], "r") as file:
        private_key = RSA.importKey(file.read())

    signer = PKCS1_v1_5.new(private_key)
    signature = base64.b64encode(signer.sign(digest))

    return ",".join(
        [
            KEYID_FDN,
            'algorithm="sha256RSA"',
            'headers="' + signature_headers + '"',
            'signature="' + signature.decode("utf-8") + '"',
        ]
    )


def get_certificate():
    with open(SIGNING_CERTS[0], "r") as file:
        data = file.read().replace("\n", "")
    return data


def make_headers(
    method, url, request_id, body, content_type="application/json", extra_headers={}
):
    headers = {
        **extra_headers,
        "request-target": url,
        "Accept": "application/json",
        "Content-Type": content_type,
        "Date": get_current_rfc_1123_date(),
        "Digest": get_digest(body),
        "X-Request-ID": request_id,
        "PSU-IP-Address": PSU_IP_ADDRESS,
    }
    return {
        **headers,
        "Signature": get_signature(method, headers),
        "TPP-Signature-Certificate": get_certificate(),
    }


def create_consent(iban, valid_until):
    body = {
        "access": {
            "accounts": [{"iban": iban, "currency": "EUR"}],
            "balances": [{"iban": iban, "currency": "EUR"}],
            "transactions": [{"iban": iban, "currency": "EUR"}],
            "availableAccounts": None,
            "availableAccountsWithBalances": None,
            "allPsd2": None,
        },
        "combinedServiceIndicator": False,
        "recurringIndicator": True,
        "validUntil": valid_until.strftime("%Y-%m-%d"),
        "frequencyPerDay": 4,
    }
    body = json.dumps(body)

    url = f"{API_URL_PREFIX}consents"
    request_id = str(uuid.uuid4())

    headers = make_headers("post", url, request_id, body)

    r = requests.post(url, data=body, headers=headers, cert=TLS_CERTS)
    if r.status_code != 201:
        raise requests.ConnectionError("Expected status code 201, but received {}.".format(r.status_code))
    else:
        r = r.json()

    oauth_url = "".join(
        [
            OAUTH_URL_PREFIX,
            "client_id=" + CLIENT_ID + "&",
            "state={}&",
            "scope=" + "AIS:" + r["consentId"] + "&",
            "code_challenge=12345&",
            "code_challenge_method=Plain&",
            "redirect_uri=" + REDIRECT_URL,
        ]
    )
    return r["consentId"], oauth_url


def retrieve_access_token(access_code):
    body = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": access_code,
        "code_verifier": "12345",  # TODO
        "state": "state12345",  # TODO
        "redirect_uri": REDIRECT_URL,
    }
    body = urlencode(body, doseq=False)

    request_id = str(uuid.uuid4())

    headers = make_headers("post", ACCESS_TOKEN_URL, request_id, body,
        content_type="application/x-www-form-urlencoded;charset=UTF-8",
    )

    r = requests.post(ACCESS_TOKEN_URL, data=body, headers=headers, cert=TLS_CERTS)
    if r.status_code != 200:
        raise requests.ConnectionError("Expected status code 200, but received {}.".format(r.status_code))
    else:
        return r.json()


def retrieve_consent_details(consent_id, access_token):
    url = f"{API_URL_PREFIX}consents/{consent_id}"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={"Authorization": f"Bearer {access_token}"},
    )

    r = requests.get(url, data="", headers=headers, cert=TLS_CERTS)
    if r.status_code != 200:
        raise requests.ConnectionError("Expected status code 200, but received {}.".format(r.status_code))
    else:
        return r.json()


def delete_consent(consent_id, access_token):
    url = f"{API_URL_PREFIX}consents/{consent_id}"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={"Authorization": f"Bearer {access_token}"},
    )

    r = requests.delete(url, data="", headers=headers, cert=TLS_CERTS)
    if r.status_code != 204:
        raise requests.ConnectionError("Expected status code 204, but received {}.".format(r.status_code))
    else:
        return r.json()


def read_available_accounts(consent_id, access_token):
    url = f"{API_URL_PREFIX}accounts?withBalance=true"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=TLS_CERTS)
    return r.json()


def read_transaction_list(consent_id, access_token, account_id, date_from):
    booking_status = "booked"  # booked, pending or both
    with_balance = "true"

    url = (f"{API_URL_PREFIX}accounts/{account_id}/"
           f"transactions?bookingStatus={booking_status}&dateFrom={date_from}&"
           f"withBalance={with_balance}&download=true")
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=TLS_CERTS)
    if r.status_code != 200:
        raise requests.ConnectionError("Expected status code 200, but received {}.".format(r.status_code))
    else:
        return r.content


def read_account_information(consent_id, access_token):
    url = f"{API_URL_PREFIX}accounts"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=TLS_CERTS)
    if r.status_code != 200:
        raise requests.ConnectionError("Expected status code 200, but received {}.".format(r.status_code))
    else:
        return r.json()


def read_transaction_details(consent_id, access_token, account_id, transaction_id):
    url = f"{API_URL_PREFIX}accounts/{account_id}/transactions/{transaction_id}"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=TLS_CERTS)
    return r.json()


if __name__ == "__main__":
    # sandbox_signing = get_cert_data("xs2a_sandbox_bngbank_client_signing.cer")
    # own_signing = get_cert_data("test_public.cer")
    # get_cert_data(TLS_CERTS[0])

    consent_id = create_consent(
        iban="NL34BNGT5532530633",
        valid_until=datetime(2022, 1, 1)
    )
    access_token = retrieve_access_token()
    consent_details = retrieve_consent_details(consent_id, access_token)
    account_information = read_account_information(consent_id, access_token)
    # Because we will always link one account per municipality... Right?
    assert len(account_information["accounts"]) == 1
    account_id = account_information["accounts"][0]["resourceId"]
    transactions = read_transaction_list(consent_id, access_token, account_id, date_from="2018-01-01")
    transaction_id = transactions["transactions"]["booked"][0]["transactionId"]
    # Does not seem to contain more info than what is already returned by read_transaction_list.
    transaction_details = read_transaction_details(consent_id, access_token, account_id, transaction_id)
