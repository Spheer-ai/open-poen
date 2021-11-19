# Migration
Notes on getting Open Poen online.

## Initialize and prepare a VM for production
Edit paths and variable names to suit your own environment.

Steps:
1. Create a Ubuntu (20.04) VM in Azure. Download the SSH key.

2. If permissions for the key are too open:
    `sudo chmod 600 ~/.ssh/OpenPoenVM_key.pem`

3. Connect
    `ssh -i ~/.ssh/OpenPoenVM_key.pem azureuser@20.61.185.93`

4. Install Docker and Docker Compose on the VM.
    [Instructions Docker](https://docs.docker.com/engine/install/ubuntu/)
    [Instructions Docker Compose](https://docs.docker.com/compose/install/)

5. Transfer Open Poen from your own pc to the VM.
    `sudo scp -i ~/.ssh/OpenPoenVM_key.pem -r /home/mark/Development/open-poen azureuser@20.61.185.93:/home/azureuser/`

6. Start Open Poen on the VM.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose up`

7. Build the frontend and migrate the database schema.
    `sudo docker exec poen_node_1 yarn`
    `sudo docker exec poen_node_1 yarn prod`
    `sudo docker exec poen_app_1 flask db upgrade`

8. Set the right values in config.py

9. Attach to the nginx container and install SSL certificates.
    `sudo docker exec -it poen_nginx_1 /bin/ash`
    `certbot --nginx -d openpoen.nl -d www.openpoen.nl`

10. Set a cronjob for certificate renewal and detach.
    `0 12 * * * /usr/bin/certbot renew --quiet`
    `exit`

11. Stop Open Poen.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose down`

12. Replace the nginx config file for the one that enables SSL.
    `cd /home/azureuser/open-poen/nginx/conf.d`
    `sudo rm default.conf`
    `sudo mv ssl_configuration default.conf`

13. Setup SMTP for mail while we are at it.
    Edit `config.py` and fill in MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME and MAIL_PASSWORD.

14. Create an app in bunq's developer portal. You need to pay a monthly fee for this. You'll be prompted for this when you go to Profile -> Settings -> Security -> Developers -> OAuth in bunq's app. I found this very obtuse.

16. also fill in the redirect url in this app. Make sure it matches the redirect url in this application exactly. This included a trailing slash.

17. Linkup the application with bunq.
    Edit `config.py` and fill in BUNQ_CLIENT_ID and BUNQ_CLIENT_SECRET.

18. Restore attachments and user images.
    `scp -i ~/.ssh/OpenPoenVM_key.pem ./* azureuser@"$openpoenip":/home/azureuser/open-poen/upload/transaction-attachment`
    `scp -i ~/.ssh/OpenPoenVM_key.pem ./* azureuser@"$openpoenip":/home/azureuser/open-poen/upload/user-image`

19. Restore database.
    `sudo docker start poen_db_1`
    `sudo docker exec -it poen_db_1 bash`
    `dropdb -U flaskuser openpoendb`
    `createdb -U flaskuser openpoendb`
    `gunzip < Tuesday-postgresdump-daily.sql.gz | psql -U flaskuser openpoendb`

20. Setup a cronjob for retrieving payments.

21. Setup a cronjob for doing backups.

22. Start Open Poen. Make sure a new container is built for nginx.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose up`

23. Open Poen should be running properly now.
