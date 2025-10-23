#!/bin/bash
# -------------------------------
# Streamlit + Nginx + SSL Deploy
# -------------------------------
 
# Variables
APP_DIR="/home/ec2-user/Streamlit_UI_EI"
VENV_DIR="$APP_DIR/venv"
APP_FILE="app.py"
DOMAIN="10.94.74.222"
STREAMLIT_PORT=8501
USER="ubuntu"
 
# 1️⃣ Update & install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx git
 
# 2️⃣ Setup virtual environment
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
 
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install streamlit
 
# Install extra requirements if requirements.txt exists
if [ -f "$APP_DIR/requirements.txt" ]; then
    pip install -r "$APP_DIR/requirements.txt"
fi
 
deactivate
 
# 3️⃣ Configure Nginx
NGINX_CONF="/etc/nginx/sites-available/streamlit.conf"
 
sudo tee $NGINX_CONF > /dev/null <<EOL
server {
    listen 80;
    server_name $DOMAIN;
 
    location / {
        proxy_pass http://127.0.0.1:$STREAMLIT_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL
 
sudo ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
 
# 4️⃣ Install SSL via Certbot
sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN --redirect
 
# 5️⃣ Setup Streamlit as systemd service
SERVICE_FILE="/etc/systemd/system/streamlit.service"
 
sudo tee $SERVICE_FILE > /dev/null <<EOL
[Unit]
Description=Streamlit App
After=network.target
 
[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/streamlit run $APP_FILE --server.port $STREAMLIT_PORT
Restart=always
 
[Install]
WantedBy=multi-user.target
EOL
 
sudo systemctl daemon-reload
sudo systemctl enable streamlit
sudo systemctl start streamlit
 
# 6️⃣ Finish
echo "✅ Deployment completed!"
echo "Visit: https://$DOMAIN"








# #!/bin/bash 
# # ------------------------------- 
# # Streamlit + Nginx + SSL Deploy 
# # -------------------------------
# # Variables
# APP_DIR="/home/ec2-user/Streamlit_UI_EI"
# VENV_DIR="$APP_DIR/venv"
# APP_FILE="app.py"
# DOMAIN="10.94.74.222"
# STREAMLIT_PORT=8501
# USER="ubuntu"
# # 1️⃣ Update & install dependenciessudo apt update
# sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx git
# # 2️⃣ Setup virtual environment if [ ! -d "$VENV_DIR" ]; then    python3 -m venv "$VENV_DIR"fisource "$VENV_DIR/bin/activate"
# pip install --upgrade pip
# pip install streamlit
# # Install extra requirements 
# # if requirements.txt exists 
# if [ -f "$APP_DIR/requirements.txt" ]; then    
#     pip install -r "$APP_DIR/requirements.txt"
# fi
# deactivate
# # 3️⃣ Configure Nginx
# NGINX_CONF="/etc/nginx/sites-available/streamlit.conf"
# sudo tee $NGINX_CONF > /dev/null <<EOL
# server {
#     listen 80;
#     server_name $DOMAIN;

#     location / {
#         proxy_pass http://127.0.0.1:$STREAMLIT_PORT;
#         proxy_set_header Host \$host;
#         proxy_set_header X-Real-IP \$remote_addr;
#         proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto \$scheme;
#     }
# }
# EOL
# sudo ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
# sudo nginx -t
# sudo systemctl restart nginx
# # 4️⃣ Install SSL via Certbot
# sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN --redirect
# # 5️⃣ Setup Streamlit as systemd service
# SERVICE_FILE="/etc/systemd/system/streamlit.service"
# sudo tee $SERVICE_FILE > /dev/null <<EOL
# [Unit]
# Description=Streamlit App
# After=network.target

# [Service]
# User=$USER
# WorkingDirectory=$APP_DIR
# ExecStart=$VENV_DIR/bin/streamlit run $APP_FILE --server.port $STREAMLIT_PORT
# Restart=always

# [Install]
# WantedBy=multi-user.target
# EOL
# sudo systemctl daemon-reload
# sudo systemctl enable streamlit
# sudo systemctl start streamlit
# # 6️⃣ Finish 
# echo "✅ Deployment completed!" 
# echo "Visit: https://$DOMAIN"