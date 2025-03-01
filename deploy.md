# Deploying the Inventory Project to AWS

Below is a step-by-step outline of how I deployed the Inventory Django project to an AWS EC2 instance using **gunicorn**, **Nginx**, and **systemd** for process management. It also covers configuring environment variables, collecting static files, managing the firewall, and more, based on my terminal history.

---

## 1. Update and Install Dependencies

1. **Update apt packages:**
   ```bash
   sudo apt update
   ```

2. **Check Python version:**
   ```bash
   python --version
   ```

3. **Install Python packages:**
   ```bash
   sudo apt install python3-django
   sudo apt install python3-pip python3-venv
   ```

4. **(Optional) Install system libraries:**
   ```bash
   sudo apt install python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx curl
   ```

## 2. Clone the Repository
   ```bash
   git clone https://github.com/k1muza/inventory.git
   cd inventory
   ```

## 3. Create a Virtual Environment
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

## 4. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```

## 5. Set Up Environment Variables
   ```bash
   nano .env
   ```

   Typical variables include:
   ```bash
   SECRET_KEY=your-secret-key
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   DATABASE_URL=sqlite:///db.sqlite3 # or 'postgres://user:pass@localhost/db'
   ```

## 6. Migrate Database
   ```bash
   source venv/bin/activate
   python manage.py migrate
   ```

## 7. Collect Static Files
   ```bash
   python manage.py collectstatic --noinput
   ```

## 8. Install and Configure Gunicorn
#### 8.1 Install Gunicorn
   ```bash
   pip install gunicorn psycopg2-binary
   ```

#### 8.2 Test Gunicorn
   ```bash
   gunicorn --bind 0.0.0.0:8000 core.wsgi
   [ctrl+c]
   ```

#### 8.3 Configure Gunicorn
   ```bash
   sudo nano /etc/systemd/system/gunicorn.service
   ```

   ```bash
   [Unit]
    Description=gunicorn daemon
    Requires=gunicorn.socket
    After=network.target

    [Service]
    User=ubuntu
    Group=www-data
    WorkingDirectory=/home/ubuntu/inventory
    ExecStart=/home/ubuntu/inventory/venv/bin/gunicorn \
            --access-logfile - \
            --workers 3 \
            --bind unix:/run/gunicorn.sock \
            core.wsgi:application

    [Install]
    WantedBy=multi-user.target
   ```

#### 8.4 Enable and Start Gunicorn
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start gunicorn
   sudo systemctl enable gunicorn
   sudo systemctl status gunicorn
   ```

## 9. Install and Configure Nginx
#### 9.1 Install Nginx
   ```bash
   sudo apt install nginx
   ```

#### 9.2 Configure Nginx
   ```bash
   sudo nano /etc/nginx/sites-available/inventory
   ```

   ```bash
   server {
        listen 80;
        server_name 18.201.xxx.xxx;  # or your domain name
        
        location = /favicon.ico { access_log off; log_not_found off; }
        
        location /static/ {
            root /home/ubuntu/inventory;
        }

        location / {
            include proxy_params;
            proxy_pass http://unix:/run/gunicorn.sock;
        }
    }
   ```

#### 9.3 Enable and Start Nginx
   ```bash
    sudo ln -s /etc/nginx/sites-available/inventory /etc/nginx/sites-enabled
    sudo nginx -t
    sudo systemctl restart nginx
   ```

## 10. Install and Configure Firewall
#### 10.1 Install ufw
   ```bash
   sudo ufw allow 'Nginx Full'
   ```

#### 10.2 Enable Firewall
   ```bash
   sudo ufw enable
   ```

#### 10.3 Delete port 8000
   ```bash
   sudo ufw delete allow 8000
   ```

## 11. Managing Services
- Restart gunicorn and Nginx if you change environment variables or your code:
   ```bash
   sudo systemctl restart gunicorn
   sudo systemctl restart nginx
   ```

- Check logs if things fail:
   ```bash
    sudo journalctl -u gunicorn -f
    sudo tail -f /var/log/nginx/error.log
   ```
