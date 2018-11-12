## Set up remote Git

From these instructions: http://toroid.org/git-website-howto

1) Set up git repository on local

2) On remote, add mgo.git and do git init --bare

3) In mgo.git, add to hooks/post-receive:
#!/bin/sh
GIT_WORK_TREE=/var/www/www.example.org git checkout -f
sudo service supervisor restart

4) chmod +x hooks/post-receive

5) On local, add a name for the remote
git remote add web ssh://<user>@<IP>/path/to/app.git

6) Add to ~/.ssh/config
host <IP>
 HostName <IP>
 IdentityFile ~/.ssh/<key>
 User git

7) git push web +master:refs/heads/master

8) log in to server:
ssh -i ~/.ssh/<key> <user>@<IP>



## Set up Flask with Gunicorn and Nginx

Following this: https://medium.com/ymedialabs-innovation/deploy-flask-app-with-nginx-using-gunicorn-and-supervisor-d7a93aa07c18

And this for letsencrypt: https://www.digitalocean.com/community/tutorials/how-to-secure-nginx-with-let-s-encrypt-on-ubuntu-16-04

