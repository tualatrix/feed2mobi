#!/usr/bin/env python
#coding=utf-8

from distutils.core import setup
import py2exe

includes = ["encodings", "encodings.*"]
options = {"py2exe":
            {   
                "compressed": 1,
                "optimize": 2,
                #"includes": includes,
                "bundle_files": 1
            }
          }

setup(
    name = "feed2mobi",
    version = "0.1",
    description = "feed2mobi 0.1",
    author = "jerry",
    author_email="lxb429@gmail.com",
    url="http://k.dogear.cn",

    options = options,
    zipfile=None,
    console=[{"script":"feed2mobi.py"}]
)