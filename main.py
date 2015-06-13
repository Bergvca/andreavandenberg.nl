from flask import Flask, make_response, render_template, request, flash
from flask.ext.mail import Message, Mail
import flickr_api
import datetime
from settings import *
from google.appengine.ext import db
from google.appengine.api import users, urlfetch, mail
from forms import ContactForm
from Queue import Queue
from threading import Thread

app = Flask(__name__)
app.config['DEBUG'] = True
app.secret_key = APP_SECRET_KEY
flickr_api.set_keys(api_key = FLICKR_API_KEY, api_secret = FLICKR_API_SECRET)

class Photo(db.Model):
	name = db.StringProperty()
	description = db.TextProperty()
	uid = db.StringProperty()
	photoSetId = db.StringProperty()
	photoSetName  = db.StringProperty()
	image = db.BlobProperty() 
	imageThumb = db.BlobProperty() 
	imageURL  = db.StringProperty()
	thumbURL  = db.StringProperty()
	orgImageURL = db.StringProperty()

def clearStore():
	db.delete(Photo.all())

def userIsAdmin(user):
	return user.email() in ADMINACCOUNTS

def adminAccounts():
	result = ''
	for a in ADMINACCOUNTS:
		result = a + ', ' + result
	return result

def getPhoto(p, setId, setName):
	#fetches the picture P's metadata from flickr and puts this in the datastore
	photoInfo = p.getInfo()
	photoSizes = p.getSizes()
	desc = photoInfo['description'] 
	title = photoInfo['title']
	id = p.id
	imageURL = photoSizes['Medium']['source']
	thumbURL = photoSizes['Square']['source']
	orgImageURL = photoSizes['Original']['source']
	if HOST_IMAGES_SELF:			
		imaged = urlfetch.Fetch(imageURL).content
		imageThumb = urlfetch.Fetch(thumbURL).content
	else:
		imaged = None
		imageThumb = None

	foto = Photo(name = title, 
			description = desc, 
			image = imaged, 
			uid = id, 
			photoSetId = setId, 
			photoSetName = setName, 
			imageThumb=imageThumb, 
			imageURL=imageURL,
			thumbURL=thumbURL,
			orgImageURL=orgImageURL)		
	foto.put()

@app.route('/import')
def importPage1():
	#provides the login handling of users using their google account
	user = users.get_current_user()
	if user:
		template_values = {
		      	'user': user,
		      	'is_admin': userIsAdmin(user),
		      	'logout_url': users.create_logout_url('/import'),
			'nickname' : user.nickname() }
	else:
		template_values = {
			'login_url': users.create_login_url('/import')}					
	return render_template('import.html', template_values=template_values)

@app.route('/import2')
def importPage2():
	#deletes all old image data and uses multithreading to import new image data
	user = users.get_current_user()
	if userIsAdmin(user):
		clearStore()
		user = flickr_api.Person.findByEmail(FLICKR_USER_MAIL)
		photoSets= user.getPhotosets()
		message='Import succeded'
		threads = []
		for s in photoSets:
			setId = s.id
			setName = s.title
			photos = s.getPhotos()
			for p in photos:
				threads.append(
					Thread(target=getPhoto, args=(p, setId, setName))
					)
				threads[-1].start()
				
		for t in threads:
			t.join()
	else:
		message='You are not authorised'		
	return render_template('imported.html',message=message)

@app.route('/')
def showImages():
	pageName = 'Schilderijen'
	q = Photo.all()
	q.filter("photoSetName =", pageName)
	return render_template('gallery.html',pictures=q)

@app.route('/drawings')
def showDrawings():
	pageName = 'Tekeningen'
	q = Photo.all()
	q.filter("photoSetName =", pageName)
	return render_template('gallery.html',pictures=q)

@app.route('/otherprojects')
def showOther():
	pageName = 'Andere Projecten'
	q = Photo.all()
	q.filter("photoSetName =", pageName)
	return render_template('gallery.html',pictures=q)

@app.route('/about')
def about():
	return render_template('about.html')

@app.route('/jewellery')
def sieraden():
	pageName = 'Sieraden'
	q = Photo.all()
	q.filter("photoSetName =", pageName)
	return render_template('gallery.html',pictures=q)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
	form = ContactForm()
	if request.method == 'POST':
		if form.validate() == False:
			flash('All fields are required.')
			return render_template('contact.html', form=form)
		else:
			mail.send_mail(sender=CONTACT_SENDER_MAIL,
				      to=adminAccounts(),
				      subject=form.subject.data,
				      body=form.message.data + ' ' + form.name.data + ' , Send by: ' + form.email.data)			
			return render_template('contact.html', success=True)
	elif request.method == 'GET':
		return render_template('contact.html', form=form)
	
@app.route("/imgs/<path:path>")
def images(path):
	result = db.GqlQuery("SELECT * FROM Photo WHERE uid = :1 LIMIT 1", path).fetch(1)
	resp = make_response(result[0].image)
	resp.content_type = "image/jpeg"
	return resp

@app.route("/imgsthumb/<path:path>")
def thumbs(path):
	result = db.GqlQuery("SELECT * FROM Photo WHERE uid = :1 LIMIT 1", path).fetch(1)
	resp = make_response(result[0].imageThumb)
	resp.content_type = "image/jpeg"
	return resp
	

@app.errorhandler(404)
def page_not_found(e):
 	"""Return a custom 404 error."""
 	return 'Sorry, nothing at this URL.', 404
