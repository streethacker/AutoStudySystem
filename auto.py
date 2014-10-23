#!/usr/bin/env python
#-*- coding:utf-8 -*-

import os
import hashlib
import motor
import pymongo
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
				"UserinfoFormatter" : UserinfoModule,
			},

			login_url = "/auth/login",
		)

		tornado.web.Application.__init__(self, handlers, debug=True, **settings)

		self._db = motor.MotorClient(options.db_host, options.db_port)[options.db_name]

class BaseHandler(tornado.web.RequestHandler):
	@tornado.gen.coroutine
	def prepare(self):
		DEFAULT_TIMEDELTA_BY_DAYS = 10

		username = self.get_secure_cookie("username")

		if username:
			self._current_user = yield self.db["users"].find_one({"username":username})
	
		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		cursor = self.db["blogs"].find({"date": {"$gt":_date_point}}).sort("views", pymongo.DESCENDING).limit(3)
		self._elites = yield cursor.to_list(length=3)

	@property
	def db(self):
		return self.application._db

	@property
	def elites(self):
		if not hasattr(self, '_elites'):
			raise tornado.web.HTTPError(500)
		return self._elites

	def _resolve_pwd(self, password, algorithms="md5"):
		try:
			encrypt = getattr(hashlib, algorithms)(password).hexdigest()
		except AttributeError:
			raise tornado.web.HTTPError(500)

		return encrypt

	def _resolve_page(self, pagesize, records):
		current_page = self.get_argument("page_id", 1)
		if records == 0:
			current_page = total_page = 0
			return (current_page, total_page)

		if records < pagesize:
			current_page = total_page = 1
			return (current_page, total_page)

		if records % pagesize > 0:
			total_page = records / pagesize + 1
			return (current_page, total_page)

class LoginHandler(BaseHandler):
	def get(self):
		status = self.get_argument("status", "")
		self.render("login.html", elites=self.elites, status=status)

	@tornado.gen.coroutine
	def post(self):
		username = self.get_argument("username", "")
		password = self._resolve_pwd(self.get_argument("password", ""))

		_user_info = yield self.db["users"].find_one({"username":username})

		if not _user_info:
			self.redirect("/auth/login?" + urllib.urlencode(dict(status=1)))  #username does not exist
			return

		_auth_flag = True if _user_info["password"] == password else False

		if not _auth_flag:
			self.redirect("/auth/login?" + urllib.urlencode(dict(status=2)))  #password incorrect
			return

		self.set_secure_cookie("username", username, expires_days=1)
		self.redirect(self.get_argument("next", "/"))

class RegisterHandler(BaseHandler):
	def get(self):
		status = self.get_argument("status", "")
		self.render("register.html", elites=self.elites, status=status)

	@tornado.gen.coroutine
	def post(self):
		username = self.get_argument("username", "")
		password = self._resolve_pwd(self.get_argument("password", ""))
		email = self.get_argument("email", "")

		_user_info = yield self.db["users"].find_one({"username":username})

		if _user_info:
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

		self.redirect("/auth/login") #register successfully, redirect to login

class LogoutHandler(BaseHandler):
	def get(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")

class RootHandler(BaseHandler):
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 10 
		
		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		total_records = yield self.db["blogs"].find({"date":{"$gt":_date_point}}).count()

		current_page, total_page = self._resolve_page(DEFAULT_PAGESIZE, total_records)

		_cursor = self.db["blogs"].find({"date":{"$gt":_date_point}}).\
				sort("date", pymongo.DESCENDING).\
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
		blog_id = self.get_argument("blog_id", "")

		article = yield self.db["blogs"].find_one({"_id":ObjectId(blog_id)})
		self.render("blog.html", elites=self.elites, article=article)

		article["views"] += 1  #views count plus one
		self.db["blogs"].save(article)

class DizHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 10

		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		total_records = yield self.db["quizzes"].find({"date":{"$gt":_date_point}}).count()

		current_page, total_page = self._resolve_page(DEFAULT_PAGESIZE, total_records)

		_cursor = self.db["quizzes"].find({"date":{"$gt":_date_point}}).\
				sort("date", pymongo.DESCENDING).\
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
			"title": self.get_argument("title", ""),
			"body" : self.get_argument("body", ""),
			"date" : datetime.datetime.now(),
			"from" : self.current_user["username"],
		}

		_id = yield self.db["quizzes"].insert(_entry)
		
		if not isinstance(_id, ObjectId):
			raise tornado.web.HTTPError(500)

		self.redirect("/diz")
	
class AnswerHandler(BaseHandler):
	@tornado.gen.coroutine
	def prepare(self):
		yield super(AnswerHandler, self).prepare()  #prepare() here returns a generator, not to execute unless yield it.
		self._quiz_id = self.get_secure_cookie("quiz_id")

	@property
	def quiz_id(self):
		#if quiz_id is found in query string
		#then return it, and set/reset the Cookie
		#with the new one
		_flag = self.get_argument("quiz_id", "")
		if _flag:
			self._quiz_id = _flag
			self.set_secure_cookie("quiz_id", self._quiz_id)
		return self._quiz_id

	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 3

		quiz = yield self.db["quizzes"].find_one({"_id":ObjectId(self.quiz_id)})

		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		total_records = yield self.db["answers"].find({"to":ObjectId(self.quiz_id),"date":{"$gt":_date_point}}).count()

		current_page, total_page = self._resolve_page(DEFAULT_PAGESIZE, total_records)

		_cursor = self.db["answers"].find({"to":ObjectId(self.quiz_id),"date":{"$gt":_date_point}}).\
				sort("date", pymongo.DESCENDING).\
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
			"from" : self.current_user["username"],
			"to" : ObjectId(self.quiz_id),
			"body" : self.get_argument("body", ""),
			"praise" : 0,
			"date" : datetime.datetime.now(),
		}

		_id = yield self.db["answers"].insert(_entry)

		if not isinstance(_id, ObjectId):
			raise tornado.web.HTTPError(500)

		self.redirect("/answer")

class ExamHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		DEFAULT_PAGESIZE = 10
		DEFAULT_TIMEDELTA_BY_DAYS = 30

		_date_point = datetime.datetime.now() - datetime.timedelta(days=DEFAULT_TIMEDELTA_BY_DAYS)
		total_records = yield self.db["exams"].find({"date":{"$gt":_date_point}}).count()

		current_page, total_page = self._resolve_page(DEFAULT_PAGESIZE, total_records)

		_cursor = self.db["exams"].find({"date":{"$gt":_date_point}}).\
				sort("date", pymongo.DESCENDING).\
				skip((int(current_page)-1) * DEFAULT_PAGESIZE).\
				limit(DEFAULT_PAGESIZE)

		exams = yield _cursor.to_list(length=DEFAULT_PAGESIZE)

		self.render("exam.html",
			elites = self.elites,
			current_page = current_page,
			total_page = total_page,
			exams = exams,
		)

class PaperHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def get(self):
		paper_id = self.get_argument("paper_id", 1)
		exam = yield self.db["exams"].find_one({"_id":ObjectId(paper_id)})
	
		#exam["test"] contains a list _id refer to the issues
		#query with $in, which will iterate all these _ids
		_cursor = self.db["issues"].find({"_id":{"$in":exam["tests"]}})

		tests = yield _cursor.to_list(length=30)

		self.render("paper.html",
			elites = self.elites,
			exam = exam,
			tests = tests,
		)

		exam["views"] += 1
		self.db["exams"].save(exam)
		

class ResultHandler(BaseHandler):
	@tornado.web.authenticated
	@tornado.gen.coroutine
	def post(self):
		result = []
		
		try:
			self.request.arguments.pop("_xsrf")
		except KeyError:
			logging.warning("error pop operation")

		for (_key, _checked_pairs) in self.request.arguments.iteritems():
			_checked_option, _id = _checked_pairs[0], _checked_pairs[1]
			_issue = yield self.db["issues"].find_one({"_id":ObjectId(_id)})

			if _issue["correct"] == _checked_option:
				result.append(_key)

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
	def render(self, index, test):
		return self.render_string("modules/stem.html", index=index, test=test)

class UserinfoModule(tornado.web.UIModule):
	def render(self):
		return self.render_string("modules/userinfo.html")

if __name__ == "__main__":
	tornado.options.parse_command_line()
	app = Application()
	app.listen(options.port)
	tornado.ioloop.IOLoop.instance().start()
