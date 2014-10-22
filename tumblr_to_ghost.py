import time
import math
import re
import logging

import requests
import pandoc
from unidecode import unidecode


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
        self.ghost_tags = []
        self.posts_tags = []

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
        limit = 40
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
        post_id = 0

        logger.debug('Creating Ghost export for Tumblr posts')

        for post in posts:
            post_id += 1
            doc = pandoc.Document()

            body = self.create_body(post)

            doc.html = unidecode(body)

            tumblr_tags.extend(post['tags'])

            new_tags = self.create_tags(set(tumblr_tags))

            timestamp = post['timestamp'] * 1000

            title = self.create_title(post)

            if post['slug']:
                slug = post['slug']
            else:
                title_slug = title.lower().split(' ')
                slug = '{}-{}'.format('-'.join(title_slug), post_id)

            temp_post = {
                'id': post_id,
                'title': title,
                'slug': slug,
                'markdown': body,
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
            }

            ghost_posts.append(temp_post)

            self.create_post_tags(temp_post, new_tags)

        export_object = {
            'meta': {
                'exported_on': int(time.time()) * 1000,
                'version': '000'
            },
            'data': {
                'posts': ghost_posts,
                'tags': self.ghost_tags,
                'posts_tags': self.posts_tags
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
            title = post['text'].replace('&#8217;', '\'')
        elif post.get('title'):
            title = post.get('title')
        if title == "Text":
            clean_tags = re.compile(r'<.*?>')
            title = clean_tags.sub('', post['body'])

        # Truncate if necessary.
        max_length = 140

        title = unidecode(title)

        if len(title) > max_length:
            title = '{}...'.format(
                ' '.join(title[:max_length+1].split(' ')[0:-1])
            )

        return title

    def create_body(self, post):
        type = post['type']

        logger.debug('Getting body for post of {} type'.format(type))

        if type == 'text':
            body = u'{}'.format(post['body'])
        elif type == 'link':
            description = unidecode(post['description'])
            body = ''.join([
                '<strong><a href="{}">{}</a></strong>',
                '<p>{}</p>',
                '']).format(post['url'], post['title'], description)
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
            if 'source' in post:
                body += post['source']
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
        tag_id = self.ghost_tags[-1]['id'] if len(self.ghost_tags) > 0 else 0

        for tag in tumblr_tags:
            tag_slug = '-'.join(tag.lower().strip(',').split(' '))
            if tag_slug not in self.used_tags:
                now = int(time.time()) * 1000
                tag_id += 1

                temp_tag = {
                    'id': tag_id,
                    'name': tag.title(),
                    'slug': tag_slug,
                    'description': None,
                    'parent_id': None,
                    'meta_title': None,
                    'meta_description': None,
                    'created_at': now,
                    'created_by': 1,
                    'updated_at': now,
                    'updated_by': 1
                }
                ghost_tags.append(temp_tag)
                self.ghost_tags.append(temp_tag)
                self.used_tags.append(tag_slug)

        return ghost_tags

    def create_post_tags(self, post, tags):

        for tag in tags:
            self.posts_tags.append({
                'post_id': post['id'],
                'tag_id': tag['id']
            })
