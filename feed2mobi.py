#!/usr/bin/env python
#coding=utf-8

import hashlib
import os
import time,datetime
import re
import urllib
import string
import uuid
import socket
import urllib2
import logging
import Image

import feedparser
from BeautifulSoup import BeautifulSoup, Tag

from utils import template
from utils import escape
from utils.selector import HtmlXPathSelector
from utils.filenames import ascii_filename

import utils.options
from utils.options import define, options

import encodings
encodings.aliases.aliases['gb2312'] = 'gb18030'

CONTENT_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"> 
    <title>{{ title }}</title>
    <style type="text/css">
        .entry{
            margin:15px 0;
        }
        .lastUpdated{
            color:gray;
        }
        .feedEntryContent{
            margin-top:10px;
        }
    </style>
</head>
<body>
    <div id="feedContent">
        {% for entry in entries %}
        <div class="entry">
            <a name="#id_{{ entry['index'] }}"></a>
            <h4>
                <a href="{{ entry['link'] }}">{{ entry['title'] }}</a>
                <small class="lastUpdated">{{ entry['updated'] }}</small>
            </h4>
            
            <div class="feedEntryContent">
                {{ entry['summary'] }}
            </div>
        </div>
        {% end %}
    </div>
    <mbp:pagebreak></mbp:pagebreak>
</body>
</html>
"""

TOC_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"> 
    <title>{{ title }}</title>
</head>
<body>
    <div>
     <h1><b>目录</b></h1>
     <h2>Content</h2><br />
    <ol>
    {% for entry in entries %}<li><a href="content.html#id_{{ entry['index'] }}">{{ entry['title'] }}</a></li>{% end %}
    </ol>
    </div>
</body>
</html>
"""

COVER_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"> 
    <title>{{ title }}</title>
</head>
<body>
    <center>
        {% if logo_image %}<img src="{{ logo_image }}" /><br />{% end %}
        <h1 id="feedTitleText">{{ title }}</h1><br />
        {{ create_time }}
    </center>
</body>
</html>
"""

NCX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
	"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="zh-CN">
<head>
<meta name="dtb:uid" content="BookId"/>
<meta name="dtb:depth" content="2"/>
<meta name="dtb:totalPageCount" content="0"/>
<meta name="dtb:maxPageNumber" content="0"/>
</head>
<docTitle><text>{{ title }}</text></docTitle>
<docAuthor><text>feed2mobi</text></docAuthor>
  <navMap>
    {% for entry in entries %}
    <navPoint class="chapter" id="chapter_{{ entry['index'] }}" playOrder="{{ entry['index'] }}">
      <navLabel>
        <text>{{ entry['title'] }}</text>
      </navLabel>
      <content src="content.html#id_{{ entry['index'] }}"/>
    </navPoint>
    {% end %}
  </navMap>
</ncx>
"""

OPF_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uuid_id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{{ title }}({{ create_date }})</dc:title>
    <dc:language>zh-CN</dc:language>
    <!--<meta name="cover" content="My_Cover" />-->
    <dc:identifier id="uuid_id" opf:scheme="uuid">{{ uuid }}</dc:identifier>
    <dc:creator>feed2mobi</dc:creator>  
    <dc:publisher>feed2mobi</dc:publisher>
    <dc:subject></dc:subject>
    <dc:date>{{ create_time }}</dc:date>
    <dc:description></dc:description>
</metadata>
<manifest>
    <item id="cover" media-type="application/xhtml+xml" href="cover.html"></item>
    <item id="content" media-type="application/xhtml+xml" href="content.html"></item>
    <item id="toc" media-type="application/xhtml+xml" href="toc.html"></item>
    <item id="ncx" media-type="application/x-dtbncx+xml" href="toc.ncx"/>
    <!--<item id="My_Cover" media-type="image/gif" href="../wreading.jpeg"/>-->
</manifest>
	
<spine toc="ncx">
    <itemref idref="cover" linear="no"/>
    <itemref idref="content"/>
    <itemref idref="toc"/>
</spine>

<guide>
	<reference type="toc" title="toc" href="toc.html"></reference>
	<reference type="text" title="cover" href="cover.html"></reference>
</guide>
</package>
"""

def make_thumbnail(filename, size=300):
    pixbuf = Image.open(filename)

    width, height = pixbuf.size

    if height > size:
        delta = height / size
        width = int(width / delta)
        pixbuf.thumbnail((width, size), Image.ANTIALIAS)
        pixbuf.save(filename)

def get_image_size(filename):
    pixbuf = Image.open(filename)

    return pixbuf.size

class Feed2mobi:
    
    template_path = 'templates/'
    data_dir = ''
    templates = {
        'content.html':CONTENT_TEMPLATE,
        'toc.html':TOC_TEMPLATE,
        'toc.ncx':NCX_TEMPLATE,
        'cover.html':COVER_TEMPLATE,
        'content.opf':OPF_TEMPLATE,
    }
        
    user_agent = "Feedfetcher-Google; Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/533.4 (KHTML, like Gecko) Chrome/5.0.375.99 Safari/533.4"
    accept_language = "zh-cn,zh;q=0.7,nd;q=0.3"
    
    remove_tags = [
            dict(name='object'),
            dict(name='video'),
            dict(name='input'),
            dict(name='button'),
            #dict(name='hr'),
            #dict(name='img')
        ]
    
    remove_attributes = ['class','id','title']
    noimage = False

    def __init__(self, url, xpath=False, timeout=30,
                max_images=20,
                template_path = None,
                data_dir=None
            ):
        
        self.url = url
        self.xpath = xpath
        
        self.max_images = max_images
        
        if template_path:
            self.template_path = template_path
            
        if data_dir:
            self.data_dir = data_dir
        
        socket.setdefaulttimeout(timeout)
        logging.info("Init success")

    def create_file(self, filename):
        
        logging.info("Generate: %s" % filename)
        
        if self.template_path and os.path.isfile(self.template_path+filename):
            t = template.Loader(self.template_path).load(filename)
            
        else:
            t = template.Template(self.templates[filename])
        
        content = t.generate(
            uuid = uuid.uuid1(),
            noimage = self.noimage,
            title = self.feed.feed.title,
            #subtitle = self.feed.feed.subtitle,
            logo_image = self.logo_image,
            entries = self.entries,
            max_index = self.max_index,
            #updated = time.strftime('%Y-%m-%d',self.feed.feed.updated_parsed),
            #info = self.feed.feed.info,
            #author = self.feed.feed.author
            create_time = time.strftime('%B %d, %Y %H:%M'),
            create_date = time.strftime('%B %d')
        )
        
        outfile = self.book_dir+filename
        
        fp = open(outfile, 'wb')
        fp.write(content)
        fp.close()

    def create_content_file(self, index):
        logging.info("Generate: content-%d.html" % (index + 1))
        filename = 'content.html'

        if self.template_path and os.path.isfile(self.template_path + filename):
            t = template.Loader(self.template_path).load(filename)
        else:
            t = template.Template(self.templates[filename])

        content = t.generate(entry=self.entries[index])

        outfile = self.book_dir + 'content-%d.html' % (index + 1)

        fp = open(outfile, 'wb')
        fp.write(content)
        fp.close()

    def down_image(self, url, referer=None):
        logging.info("Downimage: %s" % url)
        url = escape.utf8(url)
        image_guid = hashlib.sha1(url).hexdigest()
        
        x = url.split('.')
        
        ext = None
        if len(x) > 1:
            ext = x[-1]
            
            if len(ext) > 4:
                ext = ext[0:3]
                
            ext = re.sub('[^a-zA-Z]','', ext)
            ext = ext.lower()
            
            if ext not in ['jpg', 'jpeg', 'gif','png','bmp']:
                return False
        else:
            return False

        filename = 'images/' + image_guid + '.' + ext
        fullname = self.book_dir + filename
        
        if os.path.isfile(fullname) is False:
            #try:
            #    urllib.urlretrieve(url, fullname)
            #except:
            #    return False
            try:                
                req = urllib2.Request(url)
                req.add_header('User-Agent', self.user_agent)
                req.add_header('Accept-Language', self.accept_language)
                req.add_header('Referer', referer)
                response = urllib2.urlopen(req)
                
                localFile = open(fullname, 'wb')
                localFile.write(response.read())
                
                response.close()
                localFile.close()
                
            except Exception, e:
                return False

        make_thumbnail(fullname)

        return filename
    
    def get_fulltext(self, url, xpath):
        
        logging.info("GetFulltext: %s xpath:%s" % (url, xpath))
        try:
            article = self.book_dir+'articles/'
            hash = hashlib.sha1(url).hexdigest()
            
            filename = article+'%s.html' % hash
            
            if not os.path.isfile(filename):
                req = urllib2.Request(url)
                req.add_header('User-Agent', self.user_agent)
                req.add_header('Accept-Language', self.accept_language)
                response = urllib2.urlopen(req)
                
                html = response.read()
                localFile = open(filename, 'wb')
                localFile.write(html)
                localFile.close()
            else:
                localFile = open(filename, 'wb')
                html = localFile.read()
                localFile.close()
                
            html = BeautifulSoup(html).renderContents('utf-8')
            hxs = HtmlXPathSelector(html)
            
            content = hxs.select(xpath).extract()
            
            content = ''.join(content)
            return content
        except:
            return False
    
    def absolute_path(self, url, purl):
        """将相对路径的url转换为绝对路径"""
        
        if re.match(r'^http(s)?://.*', url):
            return url
    
        paths = purl.split('/')
        url_parse = url.split('/')
        
        if not re.match(r'/.*', url) is None:
            return paths[0]+'/'+paths[1]+'/'+paths[2]+url        
        else:
            n = ''
            y = 0
            for x in paths:
                if y < len(paths)-1:
                    n = n +'/'+x
                    y = y + 1
            
            return n+'/'+url
        
    def parse_summary(self, summary, link):
        
        #summary = escape.utf8(summary)
        soup = BeautifulSoup(summary)
        
        for script in list(soup.findAll('script')):
            script.extract()
            
        for o in soup.findAll(onload=True):
            del o['onload']
            
        for script in list(soup.findAll('noscript')):
            script.extract()
            
        for attr in self.remove_attributes:
            for x in soup.findAll(attrs={attr:True}):
                del x[attr]
                
        for tag in self.remove_tags:
            for x in soup.findAll(tag['name']):
                x.extract()
                
        for base in list(soup.findAll(['base', 'iframe'])):
            base.extract()
            
        #for p in list(soup.findAll(['p', 'div'])):
        #    p['style'] = 'text-indent:2em'
        
        img_count = 1
        for img in list(soup.findAll('img')):
            
            if self.noimage or img_count >= self.max_images:
                img.extract()
            else:
                image_url = self.absolute_path(img['src'], link)
                image = self.down_image(image_url, link)

                if image:
                    width, height = get_image_size(self.book_dir + image)
                    img['src'] = image
                    img['width'] = width
                    img['height'] = height

                    # This make the image centered
                    if img.parent.name == u'p' and img.parent.attrs == []:
                        if len(img.parent.contents) == 1:
                            img.parent['class'] = 'centered'
                else:
                    img.extract()

            img_count = img_count + 1
        
        return soup.renderContents('utf-8')
        
    def parse(self):
        
        logging.info('Parse feed: %s' % self.url)
        
        referrer = "https://www.google.com/reader/view/"
        self.feed = feedparser.parse(self.url, agent=self.user_agent,referrer=referrer)
        
        if self.feed.bozo == 1:
            raise self.feed.bozo_exception

        self.ffname = ascii_filename(self.feed.feed.title)
        
        self.book_dir = '%s%s' % (self.data_dir, self.ffname)
        
        #如果目录存在换个名字
        #i,tmpdir = 1,self.book_dir
        #while True:
        #    if os.path.isdir(tmpdir):
        #        tmpdir = self.book_dir + ('(%s)' % i)
        #        i = i + 1
        #    else:
        #        self.book_dir = tmpdir
        #        break

        self.book_dir = self.book_dir + '/'
        
        if os.path.isdir(self.book_dir) is False:
            os.mkdir(self.book_dir, 0777)
            
        if os.path.isdir(self.book_dir+'images/') is False:
            os.mkdir(self.book_dir+'images/', 0777)
        
        if os.path.isdir(self.book_dir+'articles/') is False:
            os.mkdir(self.book_dir+'articles/', 0777)
        
        return self
    
    def build(self,noimage=False):
        
        self.noimage = noimage
        
        if self.feed.bozo == 1:
            raise self.feed.bozo_exception

        if 'image' in self.feed.feed and 'href' in self.feed.feed.image:
            self.logo_image = self.down_image(self.feed.feed.image.href, self.url)
        else:
            self.logo_image = False
        
        index, entries = 0, []
        for entry in self.feed.entries:
            index = index + 1

            if self.xpath:
                fulltext = self.get_fulltext(entry.link, self.xpath)
                
                if fulltext:
                    entry.summary = fulltext
            
            summary =  self.parse_summary(entry.content[0]['value'], entry.link)
            
            if 'guid' not in entry or not entry.guid:
                entry.guid = entry.link
            
            entries.append({
                    'link':entry.link,
                    'title':entry.title,
                    'author': entry.author,
                    'updated':time.strftime('%B %d, %Y %H:%M', entry.updated_parsed),
                    'summary':summary,
                    'base':entry.summary_detail.base,
                    'uuid':uuid.uuid1(),
                    'index':index
                })
    
        self.max_index = index
        self.entries = entries
        logging.info('There are %d entries/index: %d' % (len(self.entries), self.max_index))
        
        for i in xrange(self.max_index):
            self.create_content_file(i)

        self.create_file('toc.html')
        self.create_file('toc.ncx')
        self.create_file('cover.html')
        self.create_file('content.opf')
        
        if self.noimage:
            mobi_file = '%s_noimage.mobi' % self.ffname
        else:
            mobi_file = '%s.mobi' % self.ffname
        
        logging.info("Build mobi file: %s" % mobi_file)
        
        import platform
        ostype = string.lower(platform.system())
        
        if ostype == 'windows':
            os.system('kindlegen.exe %s -unicode -o %s' % (self.book_dir+"content.opf", mobi_file))
        else:
            os.popen('kindlegen %s -unicode -o %s' % (self.book_dir+"content.opf", mobi_file))
        
        return self.book_dir+mobi_file

define("url", help="feed url")
define("xpath", default=None, help="full text xpath")
define("max_images", default=10, help="max images in per item", type=int)
define("template_path", default=None, help="templates directory")
define("data_dir", default=None, help="data directory")
define("test", default=False, help="test", type=bool)
define("noimage", default=False, help="no image", type=bool)

def test():
    feeds = [
        {'url':'http://news.163.com/special/00011K6L/rss_newstop.xml', 'xpath':"//div[@id='endText']"},
        {'url':'http://www.cnbeta.com/backend.php', 'xpath':"//div[@id='news_content']"},
        {'url':'http://cn.engadget.com/rss.xml', 'xpath':False},
    ]
    
    for f in feeds:
        Feed2mobi(f['url'], f['xpath']).parse().build()

def main():
    utils.options.parse_command_line()
    
    if options.url is None:
        import sys
        args = sys.argv
        if len(args) >= 2:
            options.url = args[1]

    #if not options.test and (options.url is None or not re.match(r'/^http(s)?:\/\/[^\s]*$/', options.url)):
    #    logging.error("feed url error")
    #    sys.exit(1)

    if options.test:
       test()
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(name)-8s %(message)s',
                datefmt='%m-%d %H:%M') #, filename='log/web.log', filemode='a')
        mobifile = Feed2mobi(options.url,
                xpath=options.xpath,
                max_images=options.max_images,
                template_path=options.template_path,
                data_dir=options.data_dir,
            ).parse().build(options.noimage)
        
        print '-'*50
        print ''
        print "Output: %s" % mobifile
        print ''
    
if __name__ == '__main__':
    main()
