#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Web Content Extractor with CRF
# (c)2010 Nakatani Shuyo, Cybozu Labs Inc.

import sys, os, re, glob, pickle
from optparse import OptionParser
sys.path.append("../sequence")
from crf import CRF, Features, FeatureVector, flatten


def load_dir(dir):
    '''load training/test data directory'''

    labels = []
    texts = []
    for filename in glob.glob(os.path.join(dir, '*.html')):
        text, label = load_file(filename)
        texts.append(text)
        labels.append(label)
    return (texts, labels)

def load_file(filename):
    '''load html file'''

    f = open(filename, 'r')
    html = f.read()
    f.close()

    html = re.sub(r'(?is)<(no)?script[^>]*>.*?</(no)?script>', '', html)
    html = re.sub(r'(?is)<style[^>]*>.*?</style>', '', html)
    slices = re.split(r'(?i)(<\/(?:head|div|td|table|p|ul|li|d[dlt]|h[1-6]|form)>|<br(?:\s*\/)?>|<!-- extractcontent_(?:\w+) -->)', html)

    current_label = "head"
    blocks = [slices[0]]
    labels = [current_label]
    for i in range(1,len(slices),2):
        mt = re.match(r'<!-- extractcontent_(\w+) -->', slices[i])
        if mt:
            current_label = mt.group(1)
        else:
            blocks[-1] += slices[i]
            if len(slices[i+1].strip())<15:
                blocks[-1] += slices[i+1]
                continue
        blocks.append(slices[i+1])
        labels.append(current_label)

    print "<<", filename, len(blocks), "blocks, labels=",unique(labels), ">>"
    return ([BlockInfo(b) for b in blocks], labels)

def eliminate_tags(x):
    return re.sub(r'\s', '', re.sub(r'(?s)<[^>]+>', '', x))

class BlockInfo(object):
    def __init__(self, block):
        tags = re.findall(r'<(\w+)', block)
        self.map = dict()
        for t in tags:
            t = t.lower()
            if t in self.map:
                self.map[t] += 1
            else:
                self.map[t] = 1

        self.has_word = dict()
        self.org_text = block
        self.plain_text = eliminate_tags(block)
        notlinked_text = eliminate_tags(re.sub(r'(?is)<a\s[^>]+>.+?<\/a>', '', block))

        self.len_text = len(self.plain_text)
        self.linked_rate = 1 - float(len(notlinked_text)) / self.len_text if self.len_text > 0 else 0
        self.n_ten = len(re.findall(r'、|，', self.plain_text))
        self.n_maru = len(re.findall(r'。', self.plain_text))
        self.has_date = re.search(r'20[01][0-9]\s?[\-\/]\s?[0-9]{1,2}\s?[\-\/]\s?[0-9]{1,2}', self.plain_text) or re.search(r'20[01][0-9]年[0-9]{1,2}月[0-9]{1,2}日', self.plain_text)
        self.affi_link = re.search(r'amazon[\w\d\.\/\-\?&]+-22', block)
    def __getitem__(self, key):
        if key not in self.map: raise IndexError, key
        return self.map[key]
    def has(self, word):
        if word in self.has_word: return self.has_word[word]
        self.has_word[word] = True if re.search(word, self.plain_text, re.I) else False
        return self.has_word[word]


def unique(x):
    a = []
    b = dict()
    for y in x:
        if y not in b:
            a.append(y)
            b[y] = 1
    return a

def wce_features(LABELS):
    '''CRF features for Web Content Extractor'''
    features = Features(LABELS)
    for label in LABELS:
        # keywords
        for word in "Copyright|All Rights Reserved|広告掲載|会社概要|無断転載|プライバシーポリシー|利用規約|お問い合わせ|トラックバック|ニュースリリース|新着|無料|確認メール|コメントする|アソシエイト".split('|'):
            features.add_feature( lambda x, y, w=word, l=label: 1 if x.has(w) and y == l else 0 )
            #features.add_feature( lambda x, y, w=word, l=label: 1 if re.search(w, x.org_text, re.I) and y == l else 0 )

        # html tags
        for tag in "a|p|div|ul|ol|li|dl|dt|dd|table|tr|td|h1|h2|h3|h4|h5|h6|meta|form|input|select|option|object|img".split('|'):
            features.add_feature( lambda x, y, t=tag, l=label: 1 if t in x and y == l else 0 )

        # date & affiliate link
        features.add_feature( lambda x, y, l=label: 1 if x.has_date and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.affi_link and y == l else 0 )

        # punctuation
        features.add_feature( lambda x, y, l=label: 1 if x.n_ten>0 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_ten>1 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_ten>2 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_ten>5 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_maru>0 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_maru>1 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_maru>2 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.n_maru>5 and y == l else 0 )

        # text length
        features.add_feature( lambda x, y, l=label: 1 if x.len_text==0 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.len_text>10 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.len_text>20 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.len_text>50 and y == l else 0 )

        # linked rate
        features.add_feature( lambda x, y, l=label: 1 if x.linked_rate>0.8 and y == l else 0 )
        features.add_feature( lambda x, y, l=label: 1 if x.linked_rate<0.2 and y == l else 0 )

    # label bigram
    for label1 in features.labels:
        features.add_feature( lambda x, y, l=label1: 1 if y == l else 0 )
        features.add_feature_edge( lambda y_, y, l=label1: 1 if y_ == l else 0 )
        for label2 in features.labels:
            features.add_feature_edge( lambda y_, y, l1=label1, l2=label2: 1 if y_ == l1 and y == l2 else 0 )

    return features

def wce_output_tagging(text, label, prob, tagged_label):
    '''tagging & output'''

    if all(x=="head" for x in label):
        print "log_prob:", prob

        cur_text = [] # texts with current label
        cur_label = None
        for x in zip(tagged_label, text):
            if cur_label != x[0]:
                wce_output(cur_label, cur_text)
                cur_text = []
                cur_label = x[0]
            cur_text.append(x[1].org_text[0:64].replace("\n", " "))
        wce_output(cur_label, cur_text)
    else:
        compare = zip(label, tagged_label, text)
        print "log_prob:", prob, " rate:", len(filter(lambda x:x[0]==x[1], compare)), "/", len(compare)
        for x in compare:
            if x[0] != x[1]:
                print "----------", x[0], "=>", x[1]
                print x[2].org_text[0:400].strip()

def wce_output(label, text):
    if len(text)==0: return
    if len(text)<=7:
        for t in text: print "[%s] %s" % (label, t)
    else:
        for t in text[:3]: print "[%s] %s" % (label, t)
        print ": (", len(text)-6, "paragraphs)"
        for t in text[-3:]: print "[%s] %s" % (label, t)


def main():
    parser = OptionParser()
    parser.add_option("-d", dest="training_dir", help="training data directory")
    parser.add_option("-t", dest="test_dir", help="test data directory")
    parser.add_option("-f", dest="test_file", help="test data file")
    parser.add_option("-m", dest="model", help="model file")
    parser.add_option("-b", dest="body", action="store_true", help="output body")
    parser.add_option("-l", dest="regularity", type="int", help="regularity. 0=none, 1=L1, 2=L2 [2]", default=2)
    (options, args) = parser.parse_args()
    if not options.training_dir and not options.model:
        parser.error("need training data directory(-d) or model file(-m)")

    if options.training_dir:
        texts, labels = load_dir(options.training_dir)
        LABELS = unique(flatten(labels))
    else:
        f = open(options.model, 'r')
        LABELS, theta = pickle.loads(f.read())
        f.close()

    features = wce_features(LABELS)
    crf = CRF(features, options.regularity)

    if options.training_dir:
        fvs = [FeatureVector(features, x, y) for x, y in zip(texts, labels)]

        # initial parameter (pick up max in 10 random parameters)
        theta = sorted([crf.random_param() for i in range(10)], key=lambda t:crf.likelihood(fvs, t))[-1]

        # inference
        print "features:", features.size()
        print "labels:", len(features.labels), features.labels
        print "log likelihood (before inference):", crf.likelihood(fvs, theta)
        theta = crf.inference(fvs, theta)
        if options.model:
            f = open(options.model, 'w')
            f.write(pickle.dumps((LABELS, theta)))
            f.close()
    elif features.size() != len(theta):
        raise ValueError, "model's length not equal feature's length."

    if options.test_dir:
        test_files = glob.glob(options.test_dir + '/*')
    elif options.test_file:
        test_files = [options.test_file]
    else:
        test_files = []

    i = 0
    for filename in test_files:
        if not options.body: print "========== test = ", i
        text, label = load_file(filename)
        fv = FeatureVector(features, text)
        prob, ys = crf.tagging(fv, theta)
        tagged_label = features.id2label(ys)

        if options.body:
            for x, l in zip(text, tagged_label):
                if l == "body": print re.sub(r'\s+', ' ', re.sub(r'(?s)<[^>]+>', '', x.org_text)).strip()
        else:
            wce_output_tagging(text, label, prob, tagged_label)
        i += 1

if __name__ == "__main__":
    main()
