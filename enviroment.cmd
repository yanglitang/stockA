git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897

git config --global --unset http.proxy
git config --global --unset https.proxy

nohup python3 main.py -c ./config.ini > nohup.out 2>&1 &
