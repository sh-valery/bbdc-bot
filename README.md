# BBDC-bot
Program help to check the available slots in BBDC (Bukit Batok Driving Centre), and send notification to your phone by Telegram bot.

Course supports:
* 2B


# Note
The program is working on macOS Big Surf

# Prerequisites
* Python3
* [Docker](https://docs.docker.com/get-docker/) (headless Chrome)
* [Telegram Bot](https://t.me/botfather)

# Setup
## Pull docker image of Chrome
```sh
docker pull selenium/standalone-chrome:94.0
```

## Clone the repo
```sh
git clone https://github.com/sh-valery/bbdc-bot.git
cd bbdc-booking-bot
```

## Create your telegram bot
# todo
Follow this curls to create your bot
```sh
```

## Set the config
please fill in the followings in the `config.yaml`

* `Interval` of checking the slots (example: every 5 mins)
* BBDC `username` and `password`
* Your wanted `sessions`
* Telegram Bot `token` and `chat_id`

# Run the program
```sh
docker compose up
```

## Run seperately
### Launch Chrome container
```sh
docker run --rm -d -p 4444:4444 --shm-size=2g selenium/standalone-chrome:94.0
```
### Run the program
```sh
docker build -t bbdc-bot .
docker run --rm -it bbdc-bot
```


# Open the browser
create an ssh tunnel to the server with run selenium
```sh
ssh -L 5901:127.0.0.1:4444 -N -f root@server_ip
```

open in browser http://localhost:5901
