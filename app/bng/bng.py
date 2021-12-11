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

REDIRECT_URL = "https://nu.nl"
PSU_IP_ADDRESS = "212.178.101.162"
REQUEST_CERTS = (
    "xs2a_sandbox_bngbank_client_tls.cer",
    "xs2a_sandbox_bngbank_client_tls.key",
)
URL_PREFIX = "https://api.xs2a-sandbox.bngbank.nl/api/v1/"


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


def validate_iban(iban):
    if (iban.startswith("NL") and iban[4:7] == "BNG" and
            all([(x.isdigit()) for x in iban[8:]])):
        return
    else:
        raise ValueError(f"{iban} is not a valid IBAN.")


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

    with open("xs2a_sandbox_bngbank_client_signing.key", "r") as file:
        private_key = RSA.importKey(file.read())

    signer = PKCS1_v1_5.new(private_key)
    signature = base64.b64encode(signer.sign(digest))

    return ",".join(
        [
            ('keyId="SN=00E8B54055D929413F,CA=CN=xs2a_sandbox_bngbank_client_signing, '
            'E=klantenservice@bngbank.nl, O=BNG Bank, OU=API XS2A Sandbox, C=NL, '
            'S=South-Holland, L=The Hague, OID.2.5.4.97=PSDNL-AUT-SANDBOX"'),
            'algorithm="sha256RSA"',
            'headers="' + signature_headers + '"',
            'signature="' + signature.decode("utf-8") + '"',
        ]
    )


def get_certificate():
    with open("xs2a_sandbox_bngbank_client_signing.cer", "r") as file:
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
    validate_iban(iban)
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
        "validUntil": valid_until,
        "frequencyPerDay": 4,
    }
    body = json.dumps(body)

    url = f"{URL_PREFIX}consents"
    request_id = str(uuid.uuid4())

    headers = make_headers("post", url, request_id, body)

    r = requests.post(url, data=body, headers=headers, cert=REQUEST_CERTS).json()

    print(
        "".join(
            [
                "https://api.xs2a-sandbox.bngbank.nl/authorise?response_type=code&",
                "client_id=PSDNL-AUT-SANDBOX&",
                "state=state12345&",
                "scope=" + "AIS:" + r["consentId"] + "&",
                "code_challenge=12345&",
                "code_challenge_method=Plain&",
                "redirect_uri=" + REDIRECT_URL,
            ]
        )
    )
    return r["consentId"]


def retrieve_access_token():
    access_code = input(
        "Enter access code query string parameter from the previous step: "
    )

    body = {
        "client_id": "PSDNL-AUT-SANDBOX",
        "grant_type": "authorization_code",
        "code": access_code,
        "code_verifier": "12345",  # TODO
        "state": "state12345",  # TODO
        "redirect_uri": REDIRECT_URL,
    }
    body = urlencode(body, doseq=False)

    url = "https://api.xs2a-sandbox.bngbank.nl/token"
    request_id = str(uuid.uuid4())

    headers = make_headers("post", url, request_id, body,
        content_type="application/x-www-form-urlencoded;charset=UTF-8",
    )

    r = requests.post(url, data=body, headers=headers, cert=REQUEST_CERTS)
    return r.json()["access_token"]


def retrieve_consent_details(consent_id, access_token):
    url = f"{URL_PREFIX}consents/{consent_id}"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={"Authorization": f"Bearer {access_token}"},
    )

    r = requests.get(url, data="", headers=headers, cert=REQUEST_CERTS)
    return r.json()


def read_available_accounts(consent_id, access_token):
    url = f"{URL_PREFIX}accounts?withBalance=true"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=REQUEST_CERTS)
    return r.json()


def read_transaction_list(consent_id, access_token, account_id, date_from):
    booking_status = "both"  # booked, pending or both
    with_balance = "true"

    url = (f"{URL_PREFIX}accounts/{account_id}/"
           f"transactions?bookingStatus={booking_status}&dateFrom={date_from}&"
           f"withBalance={with_balance}")
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=REQUEST_CERTS)
    return r.json()


def read_account_information(consent_id, access_token):
    url = f"{URL_PREFIX}accounts"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=REQUEST_CERTS)
    return r.json()


def read_transaction_details(consent_id, access_token, account_id, transaction_id):
    url = f"{URL_PREFIX}accounts/{account_id}/transactions/{transaction_id}"
    request_id = str(uuid.uuid4())

    headers = make_headers("get", url, request_id, "",
        extra_headers={
            "Authorization": f"Bearer {access_token}",
            "Consent-ID": consent_id,
        },
    )

    r = requests.get(url, data="", headers=headers, cert=REQUEST_CERTS)
    return r.json()


if __name__ == "__main__":
    sandbox_signing = get_cert_data("xs2a_sandbox_bngbank_client_signing.cer")
    own_signing = get_cert_data("test_public.cer")

    consent_id = create_consent(
        iban="NL34BNGT5532530633",
        valid_until="2021-12-31"
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
