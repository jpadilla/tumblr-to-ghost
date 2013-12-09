# Tumblr to Ghost
This tool takes advantage of the exact format of the exported GhostData.json via the Ugly Debug Tools. It maps your Tumblr blog posts data to this format, creating a file that you can import directly to Ghost. It also creates all your used tags from Tumblr so you can use them later in Ghost. Check out an [example](https://gist.github.com/jpadilla/7290464) export.


## Installation
Installing on Heroku is the easiest option. Simply clone the repo, creat an app, and push.

```
$ heroku create --buildpack https://github.com/ddollar/heroku-buildpack-multi.git
$ git push heroku master
$ heroku config:set PATH=bin:/app/.heroku/python/bin:/usr/local/bin:/usr/bin:/bin
```

If you'd like to install locally, first ensure that Pandoc is installed and available.

```
$ pip install -r requirements.txt
DEBUG=True TUMBLR_API_KEY="<API KEY HERE>" python web.py
```

