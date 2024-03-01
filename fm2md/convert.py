from io import StringIO
import codecs
import os
from string import Template
from html2text import HTML2Text
from lxml import etree

def read_file(name):
    with open(name) as inp:
        result = inp.read()
    return result

# TODO: handle non-ascii chars
# TODO: set sub-head level based on map level
# TODO: Handle hyperlinks
# TODO: Handle images

class FileWriter():
    def __init__(self, target_dir):
        self.target_dir = target_dir
        self.current_chapter = StringIO()
        self.chapters = []
        self.script = StringIO()
        self.script.write('#! /usr/bin/bash\n')

    def write(self, text):
        self.current_chapter.write(text)

    def chapter(self):
        chapter = self.current_chapter.getvalue()
        self.current_chapter.close()
        if len(chapter):
            self.chapters.append(chapter)
        self.current_chapter = StringIO()

    def append_to_script(self, text):
        self.script.write(text)

    def process_images(self):
        with open(os.path.join(self.target_dir, 'copy-images.sh'), 'w') as ofile:
            ofile.write(self.script.getvalue())
        image_dir = os.path.join(self.target_dir, 'manuscript', 'images')
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

    def write_chapters(self):
        for number, chapter in enumerate(self.chapters):
            with codecs.open(os.path.join(self.target_dir, 'manuscript', 'Chapter%d.md' % number), 'w', encoding='utf8') as ofile:
                ofile.write(chapter)
        with open(os.path.join(self.target_dir, 'manuscript', 'Book.md'),'w') as ofile:
            for i in range(len(self.chapters)):
                ofile.write('Chapter%d.md\n' % i)

    def close(self):
        self.process_images()
        self.write_chapters()

class LeanpubReformatter():
    def __init__(self, target_dir, writer = None):
        self.target_dir = target_dir
        if writer is None:
            self.writer = FileWriter(target_dir)
        else:
            self.writer = writer
        self.image_dir =  'images/'
        self.relative_dir = os.path.join(target_dir, 'manuscript','images/')

    def append_text(self, text):
        self.writer.write(text)

    def chapter(self):
        self.writer.chapter()

    def add_image(self, image_location, width, image_title=''):
        if image_location.startswith('http:'):
            raise Exception('nonce error')
        if width:
            self.writer.write(Template("{width=$width%, float=right}\n").substitute(dict(width=width)))
        image_file_name = os.path.join('images',os.path.split(image_location)[1])
        self.writer.write('\n![%s](%s)' % (image_title, image_file_name))
        # no need to copy images that are already in the right place!
        if image_location.startswith(self.relative_dir):
            return
        self.writer.append_to_script('cp %s %s\n' % (image_location, self.relative_dir))

    def close(self):
        self.writer.close()


class Converter():
    def __init__(self, path_to_map, formatter=None):
        self.map_xml = read_file(path_to_map)
        directory = os.path.split(path_to_map)[0]
        if formatter is None:
            self.formatter = LeanpubReformatter(directory)
        else:
            self.formatter = formatter
        self.html_converter = HTML2Text(out=self.formatter.append_text)

    def convert_node_contents(self, depth, node):
        if node.get('TEXT'):
            self.formatter.append_text('%s %s\n\n' % (depth * '#', node.get('TEXT')))
        if node.get('LINK'):
            width = self.get_attribute(node, 'width')
            self.formatter.add_image(node.get('LINK'), width) # TODO: add title (caption)
        self.convert_html_in(node)

    def convert_node(self, node, depth=1):
        icons = node.findall('icon')
        if len(icons):
            for icon in icons:
                if icon.get('BUILTIN') == 'gohome':
                    self.formatter.append_text('\n\n{frontmatter}')
                if icon.get('BUILTIN') == 'pencil':
                    self.formatter.append_text('\n\n{mainmatter}')
        self.convert_node_contents(depth, node)
        if len(node):
            for child in node:
                self.convert_node(child, depth + 1)

    def convert_map(self):
        fm = etree.XML(self.map_xml)
        root = fm.find('node')
        for node in root:
            self.chapter()
            self.convert_node(node)
        self.chapter()
        self.formatter.close()

    def convert_html_in(self, node):
        html = node.find('richcontent')
        if html is not None and len(html):
            html_text = etree.tostring(html)
            self.html_converter.handle(html_text)

    def chapter(self):
        self.formatter.chapter()

    def get_attribute(self, node, param):
        attributes = node.xpath('attribute[@NAME="width"]')
        if len(attributes) == 0:
            return None
        return attributes[0].get('VALUE')