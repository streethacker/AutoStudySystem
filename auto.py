#!/usr/bin/env python
#-*- coding:utf-8 -*-

import os
import hashlib
import motor
import bson
import uuid
import base64
import datetime
import logging

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.options

from tornado.options import define, options

define("port", default=8000, help="server run on the given port", type=int)
define("db_host", defualt="localhost", help="database server run on the db_host", type=str)
define("db_port", defualt=27017, help="database server run on the db_port", type=int)
define("db_name", default="testdb", help="database to be used", type=str)

class Application(tornado.web.Application):
	def __init__(self):
		handlers = [
			(r"/auth/login", LoginHandler),
			(r"/auth/register", RegisterHandler),
			(r"/auth/logout", LogoutHandler),
			(r"/", RootHandler),
			(r"/blog", BlogHandler),
			(r"/diz", DizHandler),
			(r"/answer", AnswerHandler),
			(r"/exam", ExamHandler),
			(r"/paper", PaperHandler),
			(r"/result", ResultHandler),
		]

		settings = dict(
			template_path = os.path.join(os.path.dirname(__file__), "templates"),
			static_path = os.path.join(os.path.dirname(__file__), "static"),
			cookie_secret = "__TODO_:_GENERATE_YOUR_OWN_RANDOM_NUMBER_HERE__",
			xsrf_cookies = True,

			ui_modules = {
				"EliteFormatter" : EliteModule,
				"ArticleFormatter" : ArticleModule,
				"PageFormatter" : PageModule,
				"QuizFormatter" : QuizModule,
				"ExamFormatter" : ExamModule,
				"AnswerFormatter" : AnswerModule,
				"TestFormatter" : TestModule,
			},

			login_url = "/auth/login",
		)

		tornado.web.Application.__init__(self, handlers, debug=True, **settings)

		self._db = motor.MotorClient(options.db_host, options.db_port)[options.db_name]

class BaseHandler(tornado.web.RequestHandler):
	@property
	def db(self):
		return self.application._db

	def _resove_pwd(self, password, algorithms="md5"):
		try:
			encrypt = getattr(hashlib, algorithms)(password).hexdigest()
		except AttributeError:
			raise tornado.web.HTTPError(500)

		return encrypt

class LoginHandler(BaseHandler):
	def get(self):
		self.render("login.html", elites=self._elites)

	@tornado.gen.coroutine
	def post(self):
		username = self.get_argument("username")
		password = self._resove_pwd(self.get_argument("password"))


