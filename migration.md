# Migration
Notes on getting Open Poen online.

## Initialize and prepare a VM for production
Edit paths and variable names to suit your own environment.

1. Create a Ubuntu (20.04) VM in Azure. Download the SSH key.
2. If permissions for the key are too open:
    `sudo chmod 600 ~/.ssh/OpenPoenVM_key.pem`
3. Connect
    `ssh -i ~/.ssh/OpenPoenVM_key.pem azureuser@20.61.185.93`
4. Install Docker and Docker Compose on the VM.
    [Instructions Docker](https://docs.docker.com/engine/install/ubuntu/)
    [Instructions Docker Compose](https://docs.docker.com/compose/install/)
5. Transfer Open Poen from your own pc to the VM.
    `sudo scp -i ~/.ssh/OpenPoenVM_key.pem -r /home/mark/Development/open-poen azureuser@20.61.185.93`
6. Start Open Poen on the VM.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose up`
7. Build the frontend and migrate the database.
    `sudo docker exec poen_node_1 yarn`
    `sudo docker exec poen_node_1 yarn prod`
    `sudo docker exec poen_app_1 bash flask db upgrade`
8. Attach to the nginx container and install SSL certificates.
    `sudo docker exec -it poen_nginx_1 /bin/ash`
    `certbot --nginx -d openpoen.nl -d www.openpoen.nl`
9. Set a cronjob for certificate renewal and detach.
    `0 12 * * * /usr/bin/certbot renew --quiet`
    `exit`
10. Stop Open Poen.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose down`
11. Replace the nginx config file for the one that enables SSL.
    `cd /home/azureuser/open-poen/nginx/conf.d`
    `sudo rm default.conf`
    `sudo mv ssl_configuration default.conf`
12. Start Open Poen. Make sure a new container is built for nginx.
    `cd /home/azureuser/open-poen/docker`
    `sudo docker-compose up`
13. Open Poen should be running properly now.
