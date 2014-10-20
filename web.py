import os
import json

from flask import Flask, Response, render_template, request

from tumblr_to_ghost import TumblrToGhost, TumblrInfoResponseError


app = Flask(__name__)
app.debug = True if os.environ.get('DEBUG', False) else False


@app.route('/', methods=['GET', 'POST'])
def index():
    context = {}

    if request.method == 'POST':
        tumblr_url = request.form['tumblr_url']
        api_key = os.environ.get('TUMBLR_API_KEY')
        tumblr_to_ghost = TumblrToGhost(
            api_key=api_key,
            tumblr_blog_url=tumblr_url
        )

        try:
            posts = tumblr_to_ghost.get_posts()
            content_disposition = 'attachment;filename={}-ghost.json'.format(tumblr_url)

            return Response(
                json.dumps(posts),
                mimetype='application/json',
                headers={
                    'Content-Disposition': content_disposition,
                }
            )
        except TumblrInfoResponseError as e:
            context.update({
                'error': e,
                'tumblr_url': tumblr_url
            })

    return render_template('index.html', **context)


if __name__ == '__main__':
    app.run()
