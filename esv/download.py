# -*- coding: utf-8 -*-
# Author: Mike Bradley
# License:
#

import os
import aqt
import logging
import urllib
import re
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from aqt import mw
from anki.hooks import addHook, wrap
from anki.utils import stripHTML, namedtmp
import aqt.editor
# from pprint import pformat
from aqt.utils import showInfo

DECK_NAME = u'Mike_Verses'
REF_FIELD = u'Ref'
TEXT_FIELD = u'Text'
AUDIO_FIELD = u'Audio'
HINT_FIELD = u'Hint'
LOG_FILENAME = 'anki_esv_plugin.log'
ADDTL_CARDS = [u'Recognize']
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S',
                    filename=os.path.join(mw.pm.addonFolder(), 'esv', LOG_FILENAME),
                    filemode='w')
logging.debug('Logger started')

class EsvSession:
   def __init__(self, key='IP'):
      options = [
         'output-format=plain-text',
         'include-passage-references=0',
         'include-first-verse-numbers=0',
         'include-verse-numbers=0',
         'include-footnotes=0',
         'include-short-copyright=0',
         'include-copyright=0',
         'include-passage-horizontal-lines=0',
         'include-heading-horizontal-lines=0',
         'include-headings=0',
         'include-subheadings=0',
         'include-selahs=0',
         'include-content-type=0',
         'line-length=0']
      options2 = [
         'output-format=html',
         'include-passage-references=true',
         'include-first-verse-numbers=false',
         'include-verse-numbers=false',
         'include-footnotes=false',
         'include-footnote-links=false',
         'include-headings=false',
         'include-subheadings=false',
         'include-surrounding-chapters=false',
         'include-word-ids=false',
         'include-audio-link=true',
         'audio-format=mp3',
         'audio-version=hw',
         'include-short-copyright=false',
         'include-copyright=false']
      self.options = '&'.join(options)
      self.options2 = '&'.join(options2)
      self.baseUrl = 'http://www.gnpcb.org/esv/share/get/?key=%s' % (key)
      self.baseUrl2 = 'http://www.esvapi.org/v2/rest/passageQuery?key=%s' % (key)

   def doPassageQuery(self, passage):
      passage = passage.split()
      passage = '+'.join(passage)
      url = self.baseUrl + '&passage=%s&action=doPassageQuery&%s' % (passage, self.options)
      logging.info('URL: %s' %(url))
      page = urllib.urlopen(url)
      return page.read()

   def doPassageQuery2(self, passage):
      passage = passage.split()
      passage = '+'.join(passage)
      url = self.baseUrl2 + '&passage=%s&%s' % (passage, self.options2)
      logging.info('URL: %s' %(url))
      page = urllib.urlopen(url)
      return page.read()

   def query(self, ref="John 1:1"):
      ref = re.sub(r'<.*?>', '', ref)
      result1 = self.doPassageQuery2(ref)
      if result1.find("ERROR")>=0:
         self.bErrorFlag=True
         return False
      esvRef = result1
      esvMp3Link = result1
      lRefPos = esvRef.find("<h2>")+4
      rRefPos = esvRef.find("<", lRefPos)
      esvRef = esvRef[lRefPos:rRefPos]
      self.esvRef = esvRef.strip()
      lPos = esvMp3Link.find('"http')+1
      rPos = esvMp3Link.find('"', lPos)
      esvMp3Link = esvMp3Link[lPos:rPos]
      self.esvMp3Link = esvMp3Link+".mp3"
      esvText = self.doPassageQuery(ref)
      self.esvText = esvText.strip()
      self.doAllTextProcessing()
      return True

   def doAllTextProcessing(self):
      self.esvRef = self.doTextProcessing(self.esvRef)
      self.esvText = self.doTextProcessing(self.esvText)
      self.esvMp3Link = self.doTextProcessing(self.esvMp3Link)

   def doTextProcessing(self, text):
      text = unicode(text)
      text = " ".join(text.split())
      return text

'''
Lookup verse from ESV web-service and set results in current note

self should be set to Editor
'''
def getVerse(self):
   #open ESV api connection and run query against reference
   esv=EsvSession()
   if not esv.query(self.note[REF_FIELD]):
      #query did not return successfully
      showInfo("No such passage: %s" % (self.note[REF_FIELD]))
      return 

   #Retrive audio into a temporary folder
   path = namedtmp(os.path.basename(esv.esvMp3Link), True)
   urllib.urlretrieve (esv.esvMp3Link, path)

   #set note fields
   self.note[AUDIO_FIELD] = self._addMedia(path)
   self.note[TEXT_FIELD] = esv.esvText
   self.note[REF_FIELD] = esv.esvRef
   self.note[HINT_FIELD] = ",".join(esv.esvText.split()[:5]).replace(",", " ")

   #set 'y' for any additional card types that need to be generated
   for cardName in ADDTL_CARDS:
      self.note[cardName] = 'y'

   #reload note, makes things show up
   self.loadNote()

'''
This function replaces Editor.onAdvanced()

All but the last couple of lines are lifted from onAdvance(). This could be handled better
'''
def onAdvancedReplacement(self, _old):
   m = QMenu(self.mw)
   a = m.addAction(_("LaTeX"))
   a.setShortcut(QKeySequence("Ctrl+t, t"))
   a.connect(a, SIGNAL("triggered()"), self.insertLatex)
   a = m.addAction(_("LaTeX equation"))
   a.setShortcut(QKeySequence("Ctrl+t, e"))
   a.connect(a, SIGNAL("triggered()"), self.insertLatexEqn)
   a = m.addAction(_("LaTeX math env."))
   a.setShortcut(QKeySequence("Ctrl+t, m"))
   a.connect(a, SIGNAL("triggered()"), self.insertLatexMathEnv)
   a = m.addAction(_("Edit HTML"))
   a.setShortcut(QKeySequence("Ctrl+shift+x"))
   a.connect(a, SIGNAL("triggered()"), self.onHtmlEdit)
   if (self.note.model()[u"name"].upper().find("VERSE") > -1):
      a = m.addAction(_("Get verse"))
      a.setShortcut(QKeySequence("Ctrl+g, g"))
      a.connect(a, SIGNAL("triggered()"), lambda self=self: getVerse(self))
   m.exec_(QCursor.pos())
    # _old(self);

#Replace function
aqt.editor.Editor.onAdvanced=wrap(aqt.editor.Editor.onAdvanced, onAdvancedReplacement, "around")

