# task_managment_with_notifications
 Simple task managment with telegram notification


```systemd
[Unit]
Description=Prime control managment system
After=network.target

[Service]
User=mansys
Group=www-data
WorkingDirectory=/home/mansys/managment_demo
Environment="PATH=/home/mansys/managment_demo/venv/bin"
ExecStart=/home/mansys/managment_demo/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

[Install]
WantedBy=multi-user.target
```

nano /etc/systemd/system/prime_control_demo.service

sudo systemctl start prime_control_demo
sudo systemctl enable prime_control_demo
