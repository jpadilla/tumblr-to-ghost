import time
import math
import re
import logging

import requests
import pandoc


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = 'http://api.tumblr.com/v2/blog/{url}/{resource}?api_key={api_key}'


class TumblrInfoResponseError(Exception):
    pass


class TumblrToGhost(object):
    def __init__(self, api_key, tumblr_blog_url):
        logger.debug('Initializing TumblrToGhost')

        self.api_key = api_key
        self.tumblr_blog_url = tumblr_blog_url
        self.api_url = API_URL.format(
            url='{url}',
            resource='{resource}',
            api_key=self.api_key
        )

        # State
        self.used_tags = []

    def get_blog_info(self):
        url = self.api_url.format(url=self.tumblr_blog_url, resource='info')

        logger.debug('Fetching blog info from: {}'.format(url))

        r = requests.get(url)
        return r.json()

    def get_posts(self):
        try:
            blog_info = self.get_blog_info()['response']['blog']
        except TypeError:
            logger.error('Invalid Tumblr blog URL')

            raise TumblrInfoResponseError(
                'Make sure this is a valid Tumblr blog URL.'
            )

        post_count = blog_info['posts']
        offset = 0
        limit = 10
        steps = post_count / limit
        posts = []

        if post_count % limit != 0:
            steps = int(math.floor(steps) + 1)

        url = '{}{}'.format(self.api_url, '&offset={offset}&limit={limit}')

        for step in range(0, steps):
            api_url = url.format(
                url=self.tumblr_blog_url,
                resource='posts',
                offset=offset,
                limit=limit
            )

            logger.debug('Fetching posts from: {}'.format(api_url))

            r = requests.get(api_url)
            posts.extend(r.json()['response']['posts'])

            offset += limit

        return self.create_ghost_export(posts)

    def create_ghost_export(self, posts):
        ghost_posts = []
        tumblr_tags = []
        ghost_tags = []
        post_id = 0
        posts_tags = []

        logger.debug('Creating Ghost export for Tumblr posts')

        for post in posts:
            post_id += 1
            doc = pandoc.Document()

            body = self.create_body(post)

            doc.html = body.encode('ascii', 'ignore')

            tumblr_tags.extend(post['tags'])

            ghost_tags = self.create_tags(set(tumblr_tags))

            timestamp = post['timestamp'] * 1000

            title = self.create_title(post)

            if post['slug']:
                slug = post['slug']
            else:
                title_slug = title.lower().split(' ')
                slug = '{}-{}'.format('-'.join(title_slug), post_id)

            ghost_posts.append({
                'id': post_id,
                'title': title,
                'slug': slug,
                'markdown': doc.markdown,
                'html': body,
                'image': None,
                'featured': 0,
                'page': 0,
                'status': 'published',
                'language': 'en_US',
                'meta_title': None,
                'meta_description': None,
                'author_id': 1,
                'created_at': timestamp,
                'created_by': 1,
                'updated_at': timestamp,
                'updated_by': 1,
                'published_at': timestamp,
                'published_by': 1
            })

        posts_tags = self.create_post_tags(posts, ghost_tags)
        export_object = {
            'meta': {
                'exported_on': int(time.time()) * 1000,
                'version': '000'
            },
            'data': {
                'posts': ghost_posts,
                'tags': ghost_tags,
                'posts_tags': posts_tags
            }
        }

        return export_object

    def create_title(self, post):
        type = post['type']
        title = type.title()

        logger.debug('Getting title for post of {} type'.format(type))

        if type == 'photo' or type == 'audio' or type == 'video':
            if post['caption']:
                clean_tags = re.compile(r'<.*?>')
                title = clean_tags.sub('', post['caption'])
            else:
                title = type.title()
        elif type == 'answer':
            title = post['question']
        elif type == 'quote':
            title = post['text']
        elif post.get('title'):
            title = post.get('title')

        # Truncate if necessary.
        max_length = 140

        if len(title) > max_length:
            title = ' '.join(title[:max_length+1].split(' ')[0:-1])
            return '{}...'.format(title.encode('ascii', 'ignore'))

        return title

    def create_body(self, post):
        type = post['type']

        logger.debug('Getting body for post of {} type'.format(type))

        if type == 'text':
            body = u'{}'.format(post['body'])
        elif type == 'link':
            description = post['description'].encode('ascii', 'ignore')
            body = u"""
            <strong><a href="{}">{}</a></strong>
            <p>{}</p>
            """.format(post['url'], post['title'], description)
        elif type == 'photo':
            try:
                body = u'<p>{}</p>'.format(post['caption'])
            except KeyError:
                body = u''

            for photo in post['photos']:
                body += u'<p>{}</p><img src="{}">'.format(
                    photo['caption'], photo['original_size']['url'])
        elif type == 'quote':
            body = u'<blockquote><p>{}</p></blockquote>'.format(post['text'])
        elif type == 'audio':
            body = u'<p>{}</p>'.format(post['embed'])
        elif type == 'answer':
            body = post['answer']
        elif type == 'video':
            max_width = 0
            embed_code = ''
            for player in post['player']:
                if player['width'] > max_width:
                    embed_code = player['embed_code']
            body = u'<p>{}</p>'.format(embed_code)
        else:
            body = u''

        return body

    def create_tags(self, tumblr_tags):
        ghost_tags =[]
        tag_id = 0

        for tag in tumblr_tags:
            if tag not in self.used_tags:
                now = int(time.time()) * 1000
                tag_id += 1

                ghost_tags.append({
                    'id': tag_id,
                    'name': tag.title(),
                    'slug': tag,
                    'description': None,
                    'parent_id': None,
                    'meta_title': None,
                    'meta_description': None,
                    'created_at': now,
                    'created_by': 1,
                    'updated_at': now,
                    'updated_by': 1
                })

                self.used_tags.append(tag)

        return ghost_tags

    def create_post_tags(self, posts, tags):
        posts_tags = []
        post_id = 0

        for post in posts:
            post_id += 1

            for post_tag in post['tags']:
                for tag in tags:
                    if post_tag.lower() == tag['name'].lower():
                        posts_tags.append({
                            'post_id': post_id,
                            'tag_id': tag['id']
                        })

        return posts_tags
