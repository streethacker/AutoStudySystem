#!/usr/bin/env python
#-*- coding:utf-8 -*-

import os
import hashlib
import motor
import bson
import uuid
import base64
import datetime
import urllib
import logging

import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.options

from bson.objectid import ObjectId
from tornado.options import define, options

define("port", default=8000, help="server run on the given port", type=int)
define("db_host", default="localhost", help="database server run on the db_host", type=str)
define("db_port", default=27017, help="database server run on the db_port", type=int)
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
	@tornado.gen.coroutine
	def prepare(self):
		DEFAULT_TIMEDELTA_BY_DAYS = 1

		username = self.get_secure_cookie("username")
		if username:
			self._current_user = yield self.db["users"].find_one({"username":username})
	
		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		cursor = self.db["blogs"].find({"date": {"$gt":_date_point}}).sort("views", -1).limit(3)
		self._elites = yield cursor.to_list(length=3)

	@property
	def db(self):
		return self.application._db

	@property
	def elites(self):
		if not hasattr(self, '_elites'):
			raise tornado.web.HTTPError(500)
		return self._elites

	def _resove_pwd(self, password, algorithms="md5"):
		try:
			encrypt = getattr(hashlib, algorithms)(password).hexdigest()
		except AttributeError:
			raise tornado.web.HTTPError(500)

		return encrypt

class LoginHandler(BaseHandler):
	def get(self):
		status = self.get_argument("status", None)
		self.render("login.html", elites=self.elites, status=status)

	@tornado.gen.coroutine
	def post(self):
		username = self.get_argument("username")
		password = self._resove_pwd(self.get_argument("password"))

		userinfo = yield self.db["users"].find_one({"username":username})

		if not userinfo:
			self.redirect("/auth/login?" + urllib.urlencode(dict(status=1)))  #username does not exist
			return

		_auth_flag = True if userinfo["password"] == password else False

		if not _auth_flag:
			self.redirect("/auth/login?" + urllib.urlencode(dict(status=2)))  #password incorrect
			return

		self.set_secure_cookie("username", username, expires_days=1)
		self.redirect(self.get_argument("next", "/"))

class RegisterHandler(BaseHandler):
	def get(self):
		status = self.get_argument("status", None)
		self.render("register.html", elites=self.elites, status=status)

	@tornado.gen.coroutine
	def post(self):
		username = self.get_argument("username")
		password = self._resove_pwd(self.get_argument("password"))
		email = self.get_argument("email")

		userinfo = yield self.db["users"].find({"username":username})

		if userinfo:
			self.redirect("/auth/register?" + urllib.urlencode(dict(status=3)))  #username already exists
			return
		
			_entry = {
				"username" : username,
				"password" : password,
				"email" : email,
				"sculpture" : "img/avatar.png",
				"role" : 0,
				"blog_focuses" : list(),
				"quiz_focused" : list(),
			}

		_id = yield self.db["users"].insert(_entry)

		if not isinstance(_id, ObjectId):
			raise tornado.web.HTTPError(500)

		self.redirect("/auth/login?" + urllib.urlencode(dict(status=4)))  #register successfully, status=4, redirect to login

class LogoutHandler(BaseHandler):
	def get(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")

class RootHandler(BaseHandler):
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 10 
		
		current_page = self.get_argument("page_id", 1)
		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)

		total_records = yield self.db["blogs"].find({"date":{"$gt":_date_point}}).count()
		total_page = total_records % DEFAULT_PAGESIZE + total_records / DEFAULT_PAGESIZE

		_cursor = self.db["blogs"].find({"date":{"$gt":_date_point}}).\
				sort("date", -1).\
				skip((int(current_page)-1) * DEFAULT_PAGESIZE).\
				limit(DEFAULT_PAGESIZE)
		
		articles = yield _cursor.to_list(length=DEFAULT_PAGESIZE)

		self.render("index.html", 
				elites=self.elites,
				current_page = current_page,
				total_page = total_page,
				articles = articles,
		)

class BlogHandler(BaseHandler):
	@tornado.gen.coroutine
	def get(self):
		blog_id = self.get_argument("blog_id")

		article = yield self.db["blogs"].find_one({"_id":ObjectId(blog_id)})
		self.render("blog.html", elites=self.elites, article=article)

		article["views"] += 1  #views count plus one
		self.db["blogs"].save(article)

class DizHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 15
		DEFAULT_TIMEDELTA_BY_DAYS = 10
		
		current_page = self.get_argument("page_id", 1)
		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)

		total_records = yield self.db["quizzes"].find({"date":{"$gt":_date_point}}).count()
		total_page = total_records % DEFAULT_PAGESIZE + total_records / DEFAULT_PAGESIZE

		_cursor = self.db["quizzes"].find({"date":{"$gt":_date_point}}).\
				sort("date", -1).\
				skip((int(current_page)-1) * DEFAULT_PAGESIZE).\
				limit(DEFAULT_PAGESIZE)

		quizzes = yield _cursor.to_list(length=DEFAULT_PAGESIZE)

		self.render("diz.html", 
				elites = self.elites,
				current_page = current_page,
				total_page = total_page,
				quizzes = quizzes,
		)

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def post(self):
		_entry = {
			"body" : self.get_argument("body"),
			"date" : datetime.datetime.now(),
			"from" : self.current_user["_id"],
		}

		_id = yield self.db["quizzes"].insert(_entry)
		
		if not isinstance(_id, ObjectId):
			raise tornado.web.HTTPError(500)

		self.redirect("/diz")
	
class AnswerHandler(BaseHandler):
	@tornado.gen.coroutine
	def prepare(self):
		super(AnswerHandler, self).prepare()
		self._quiz_id = self.get_secure_cookie("quiz_id")

	@property
	def quiz_id(self):
		if not self._quiz_id:
			self._quiz_id = self.get_argument("quiz_id")
			self.set_secure_cookie("quiz_id", self._quiz_id)
		return self._quiz_id

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 3

		quiz = yield self.db["quizzes"].find_one({"_id":ObjectId(self.quiz_id)})

		current_page = self.get_argument("current_page", 1)

		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)

		total_records = yield self.db["quizzes"].find({"date":{"$gt":_date_point}}).count()
		total_page = total_records % DEFAULT_PAGESIZE + total_records / DEFAULT_PAGESIZE

		_cursor = self.db["quizzes"].find({"date":{"$gt":_date_point}}).\
				sort("date", -1).\
				skip((int(current_page)-1) * DEFAULT_PAGESIZE).\
				limit(DEFAULT_PAGESIZE)

		answers = yield _cursor.to_list(length=DEFAULT_PAGESIZE)

		self.render("detail.html",
				elites = self.elites,
				current_page = current_page,
				total_page = total_page,
				quiz = quiz,
				answers = answers,
		)

	@tornado.gen.coroutine
	def post(self):
		_entry = {
			"from" : self.current_user["_id"],
			"to" : ObjectId(self.quiz_id),
			"body" : self.get_argument("body"),
			"praise" : 0,
			"date" : datetime.datetime.now(),
		}

		_id = yield self.db["answers"].insert(_entry)

		if not isinstance(_id, ObjectId):
			raise tornado.web.HTTPError(500)

		self.redirect("/answer")

class ExamHandler(BaseHandler):
	pass

class PaperHandler(BaseHandler):
	pass

class ResultHandler(BaseHandler):
	pass

class EliteModule(tornado.web.UIModule):
	def render(self, elite):
		return self.render_string("modules/elite.html", elite=elite)

class ArticleModule(tornado.web.UIModule):
	def render(self, article):
		return self.render_string("modules/article.html", article=article)

class PageModule(tornado.web.UIModule):
	def render(self, current_page, total_page):
		return self.render_string("modules/page.html", current_page=current_page, total_page=total_page)

class QuizModule(tornado.web.UIModule):
	def render(self, quiz):
		return self.render_string("modules/question.html", quiz=quiz)

class ExamModule(tornado.web.UIModule):
	def render(self, exam):
		return self.render_string("modules/overview.html", exam=exam)

class AnswerModule(tornado.web.UIModule):
	def render(self, answer):
		return self.render_string("modules/answer.html", answer=answer)

class TestModule(tornado.web.UIModule):
	pass


if __name__ == "__main__":
	tornado.options.parse_command_line()
	app = Application()
	app.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()