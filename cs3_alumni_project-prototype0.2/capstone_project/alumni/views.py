from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.core.mail import EmailMessage, send_mail, send_mass_mail
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.core.exceptions import *
import datetime,calendar
from datetime import date
from django.template import RequestContext
'''
# from django.contrib.auth.models import User <- not needed, imported with 'from alumni import models'

# from alumni.models import *
#from alumni.models import Event # ? => "modele object has no attribute Event" ??
'''
from alumni.models import *
from alumni import models
from django import forms
from django.core.paginator import Paginator
from django.shortcuts import render_to_response, render
from django.core.context_processors import csrf
import re
from django.db.models import Q

class UserForm(forms.Form):
    #username = forms.CharField(max_length=50)
    first_name = forms.CharField(max_length=50, label = "First Names")
    last_name = forms.CharField(max_length=50, label = "Last Names")
    email = forms.EmailField(max_length=50, label= "Email")
    password = forms.CharField(max_length=32, widget=forms.PasswordInput, min_length=4, label="Password", help_text='min 8 characters')

class ProfileForm(forms.Form):
    degree = forms.CharField(max_length=50)
    grad_year = forms.ChoiceField(choices=[(x,x) for x in range(2017, 1970)], label="Graduation year")
    city = forms.CharField(max_length=50)
    country = forms.CharField(max_length=50)

class EditProfileForm(forms.Form):
    first_name = forms.CharField(max_length=50, label = "First Name")
    last_name = forms.CharField(max_length=50, label = "Last Name")
    email = forms.EmailField(max_length=50)
    degree = forms.CharField(max_length=50)
    grad_year = forms.ChoiceField(choices=[(x,x) for x in range(2017, 1970)], label="Graduation year")
    city = forms.CharField(max_length=50)
    country = forms.CharField(max_length=50)


class JobForm(forms.Form):
    company_name = forms.CharField(max_length=100, label="Company name")
    job_desc = forms.CharField(max_length=250, label="Job description")
    job_title = forms.CharField(max_length=100, label="Job title")
    location = forms.CharField(max_length=100, label="Location")
    start_date = forms.DateField(label="Start date" , help_text="e.g. 2015-09-23")
    end_date = forms.DateField(label="End date")


class SearchForm(forms.Form):
    # 1: user 2: Year 3: Degree 4:Company 5:Job 6:Loc
    search_item = forms.ChoiceField(choices = [('-',''),('USER','User'),('YEAR','Graduation Year'),('DEGREE','Degree'),\
                                               ('COMPANY', 'Company'), ('LOC','Physical Location')], label="Search")

class PostForm(forms.ModelForm):
    class Meta:
        model = models.Post # forms.ModelForm allows for creation of form based on the object's definition in models. (because it's a ModelForm it uses this metadata)
        # using sensible help_text tags in the model object itself, since they'll be displayed to the html form with this method 
        fields = ('title', 'text') # specify the fields of Post model actually desired in this form

# TODO
# NB - current implementation being built requires a thread to be created AND a post to be created seperately
# If a user is creating a new thread, then it would be sensible to have a form that will produce BOTH A THREAD AND A POST at the same time!
# useful reference: http://stackoverflow.com/questions/15889794/creating-one-django-form-to-save-two-models
class ThreadForm(forms.ModelForm):
    class Meta:
        model = models.Thread
        # note forum should be automatically deduced (i.e. NOT a form field), since threads can only be made within forum x
        fields = ('title',) 

class AdvertForm(forms.ModelForm):
    class Meta:
        model = models.Advert
        # fields like creating user, created date, last_updated_date should be automatically figured and NOT presented to the user on the form!
        fields = ('title', 'description', 'annual_salary', 'description', 'closing_date','contact_details', 'reference', )

class LoginForm(forms.Form):
    email = forms.EmailField(max_length=50)
    password = forms.CharField(max_length=32, widget=forms.PasswordInput)

class EventsForm(forms.Form):
    title = forms.CharField(max_length=100)
    event_type = forms.ChoiceField(choices=[('-',''),('reunion', 'reunion'), ("party", "party"), ("other", "other")])
    description = forms.CharField(max_length=140)
    year = forms.ChoiceField(choices = [(x,x) for x in range (2015,2018)])
    month = forms.ChoiceField(choices = [('-',''),('1','January'),('2','February'),('3', 'March'),('4','April'),('5','May'),\
                                         ('6','June'),('7','July'),('8', 'August'),('9','September'),('10','October'),\
                                         ('11','November'),('12','December')])
    day = forms.ChoiceField(choices = [(x,x) for x in range(1, 31)])
                            #[('1', "Monday"), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', "Thursday"), \
                                       #('5', "Friday"), ('6', 'Saturday'), ('7', "Sunday")])
    street = forms.CharField(max_length=50)
    city = forms.CharField(max_length=50)
    country = forms.CharField(max_length=50)

class EditEventsForm(forms.Form):
    title = forms.CharField(max_length=100)
    event_type = forms.ChoiceField(choices=[('-',''),('reunion', 'reunion'), ("party", "party"), ("other", "other")])
    description = forms.CharField(max_length=140)
    year = forms.ChoiceField(choices = [(x,x) for x in range (2015,2018)])
    month = forms.ChoiceField(choices = [('-',''),('1','January'),('2','February'),('3', 'March'),('4','April'),('5','May'),\
                                         ('6','June'),('7','July'),('8', 'August'),('9','September'),('10','October'),\
                                         ('11','November'),('12','December')])
    day = forms.ChoiceField(choices = [('-',''),('1', "Monday"), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', "Thursday"), \
                                       ('5', "Friday"), ('6', 'Saturday'), ('7', "Sunday")])
    street = forms.CharField(max_length=50)
    city = forms.CharField(max_length=50)
    country = forms.CharField(max_length=50)



def normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    ''' Splits the query string in invidual keywords, getting rid of unecessary spaces
        and grouping quoted words together.
        Example:

        >>> normalize_query('  some random  words "with   quotes  " and   spaces')
        ['some', 'random', 'words', 'with quotes', 'and', 'spaces']

    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)]

def get_query(query_string, search_fields):
    ''' Returns a query, that is a combination of Q objects. That combination
        aims to search keywords within a model by testing the given search fields.

    '''
    query = None # Query to search for every search term
    terms = normalize_query(query_string)
    for term in terms:
        or_query = None # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query

def isInt(foo):
    try:
        int(foo)
        return True
    except:
        return False

def search(request):  #searching function
    search = SearchForm()
    query_string = ''
    found_entries = None
    found = None
    searchText = normalize_query(request.GET['q'])[0]
    '''
    print "**************************************************************************************"
    print "searchText is ", searchText, type(searchText)
    print request.GET['search_item']
    for k,v in request.GET.iteritems():
        print k,v
    print "**************************************************************************************"
    '''
    if ('q' in request.GET) and request.GET['q'].strip():
        query_string = request.GET['q']
        if request.GET['search_item'] == "USER":
        #if request.GET['search_item'] == '1':
            # use __in for exact matches and use __contains for "LIKE" and __icontains for case-insenstive LIKE
            # use a LIST for __in , give a string / int / ... for __icontains !
            matches = User.objects.filter(Q(first_name__icontains=searchText) | Q(email__icontains=searchText) | Q(last_name__icontains=searchText)| Q(first_name__in=[searchText]) | Q(email__in=[searchText]) | Q(last_name__in=[searchText]))
            found = make_paginator(request, matches, 20)
            #found_entries = User.objects.filter(entry_query)
            #found = return_search_items("auth_user", found_entries)
        if request.GET['search_item'] == "YEAR":
        #if request.GET['search_item'] == '2':
            # check if what they entered was actually an integer! (Could ENFORCE on the form ideally... )
            #if not searchText.isdigit():
            if not isInt(searchText):
                # ideally should tell the user that they entered something stupid, but instead just show them zero matches for the search
                found = make_paginator(request, [], 20)
            else:
                matches = models.Profile.objects.filter(grad_year__in=[searchText])
                found = make_paginator(request, matches, 20)
        if request.GET['search_item'] == "DEGREE" or request.GET['search_item'] == "LOC":
        #if request.GET['search_item'] == '3' or request.GET['search_item'] == '6':
            matches = models.Profile.objects.filter(Q(degree__icontains=searchText) | Q(city__icontains=searchText) | Q(country__icontains=searchText))
            found = make_paginator(request, matches, 20)
        if request.GET['search_item'] == "COMPANY":
        #if request.GET['search_item'] == '4': # note this is a company from Job object - i.e. a piece of someone's work history not a 'jobadvert'
            matches = models.Job.objects.filter(Q(company_name__icontains=searchText) | Q(job_desc__icontains=searchText) | Q(job_title__icontains=searchText))
            found = make_paginator(request, matches, 20)
        ''' if request.GET['search_item'] == "JOB":
        #if request.GET['search_item'] == '5':
            matches = models.Advert.objects.filter(Q(city__icontains=searchText) | Q(country__icontains=searchText) | Q(title__icontains=searchText) | Q(description__icontains=searchText) | Q(reference__icontains=searchText))
            found = make_paginator(request, matches, 20)'''
    if found:
        return render_to_response('../templates/alumni/search.html',
                          { 'query_string': query_string, 'found_entries': found, 'search' : search },
                          context_instance=RequestContext(request))
    else:
        # just redirect to profile view, ideally should give a message 'not found'
        return profile(request)

def return_search_items(search_model, found_entries):
    items=[]
    for i in found_entries:
        id = str(i)
        #ids = int(id)
        #id = found_entries[i]
        cursor = connection.cursor()
        if search_model == "auth_user":
            cursor.execute('SELECT first_name, last_name, email FROM ' + search_model + ' where id = ' + id)
        elif search_model == "alumni_advert":
            cursor.execute('SELECT title, description, city, country, reference FROM ' + search_model + ' where pk = ' + id)
        elif search_model == "alumni_profile":
            cursor.execute('SELECT degree, grad_year, city, country FROM ' + search_model + ' where pk = ' + id)
        elif search_model == "alumni_job":
            cursor.execute('SELECT company_name, job_decs, job_title FROM ' + search_model + ' where pk = ' + id)
        items.append(cursor.fetchall())
    return items

def index(request):
    return HttpResponse("Hello, world. You're at the alumni index.") # TODO: get rid of this!


def main(request):
    # Main listing - all forums
    forums = models.Forum.objects.all()
    return render(request, "../templates/alumni/main.html", dict(forums=forums, user=request.user))


def add_csrf(request, **kwargs):
    d = dict(user=request.user, ** kwargs)
    d.update(csrf(request)) 
    return d

def advert(request): # (i.e. post a single advert)
    if request.method == "POST":
        form = AdvertForm(request.POST)
        if form.is_valid():
            advert = models.Advert(**form.cleaned_data)
            advert.creating_user = request.user
            # redirect them back to careers listing
            # return render_to_response("../templates/alumni/careers.html", add_csrf(request, adverts=adverts))
            advert.save()
            return careers(request)
    else:
        form = AdvertForm()
    return render(request, "../templates/alumni/advert.html", add_csrf(request, form = form))

def advert_details(request, advert_pk):
    advert = models.Advert.objects.filter(pk=advert_pk)[0]
    return render_to_response("../templates/alumni/advertDetails.html", add_csrf(request, advert = advert))

def careers(request): # jobAdverts / careers (list of them)
    adverts = models.Advert.objects.all()
    adverts = make_paginator(request, adverts, 20)
    return render_to_response("../templates/alumni/careers.html", add_csrf(request, adverts=adverts))

def make_paginator(request, items, num_items):
    # Make a generic paginator usable at forum level / thread level / and on other objects 
    paginator = Paginator(items, num_items)
    try: page = int(request.GET.get("page", '1'))
    except ValueError: page = 1
    try:
        items = paginator.page(page)
    except (InvalidPage, EmptyPage):
        items = paginator.page(paginator.num_pages)
    return items

# intentionally only allow for new forums to be created via the admin web backend. we need to dictate the terms of the discourse!
# regular joe users should be allowed to create threads and posts within the exsisting forums (of course)
def forum(request, forum_pk):
    # listing of threads in a particular forum
    threads = models.Thread.objects.filter(forum=forum_pk).order_by("-created_date") # most recent threads first!
    threads = make_paginator(request, threads, 20)
    #return render(request, "../templates/alumni/forum.html", add_csrf(request, threads=threads, pk=forum_pk))
    return render_to_response("../templates/alumni/forum.html", add_csrf(request, threads=threads, pk=forum_pk))

def thread(request, thread_pk):
    # listing of threads in a particular forum
    posts = models.Post.objects.filter(thread=thread_pk).order_by("created_date") # oldest posts first within a thread!
    posts = make_paginator(request, posts, 20)
    #return render(response, "../templates/alumni/thread.html", add_csrf(request, posts=posts, pk=thread_pk))
    return render_to_response("../templates/alumni/thread.html", add_csrf(request, posts=posts, pk=thread_pk))

# don't need a post listing function here, posts are not individual urls here, just a components of thread urls 
# the post function is used for creating a post however
def post(request, thread_pk):
    form = PostForm()
    thread = models.Thread.objects.filter(pk=thread_pk)[0]
    if request.method == "POST":
        # then they are sending data, create a new user
        form = PostForm(request.POST)
        if form.is_valid():
            post = models.Post(**form.cleaned_data)
            post.thread = thread # not a form input
            post.creating_user = request.user
            post.save()
            
            # DRY violation, but thread object not callable? better way?
            posts = models.Post.objects.filter(thread=thread_pk).order_by("created_date") # want most recent threads first, but posts should be chronological
            posts = make_paginator(request, posts, 20)
            return render_to_response("../templates/alumni/thread.html", add_csrf(request, posts=posts, pk=thread_pk))
            
            # return thread(request, thread.pk)
    else:
        # they are requesting the page / they want to post some classic vitriol
        form = PostForm()
        return render(request, '../templates/alumni/newpost.html', {'form': form})

def create_new_thread(request, forum_pk):
    # creates a thread *and* an initial post in that thread
    forum = models.Forum.objects.filter(pk=forum_pk)[0]
    if request.method == "POST":
        thread_form = ThreadForm(request.POST)
        post_form = PostForm(request.POST)
        if thread_form.is_valid() and post_form.is_valid():
            thread = models.Thread(**thread_form.cleaned_data)
            thread.forum = forum
            thread.creating_user = request.user
            thread.save()
            post = models.Post(**post_form.cleaned_data)
            post.thread = thread
            post.creating_user = request.user
            post.save()
            # go into the newly made thread
            # return thread(request, thread.pk)
            posts = models.Post.objects.filter(thread=thread_pk).order_by("created_date")
            posts = make_paginator(request, posts, 20)
            #return render(response, "../templates/alumni/thread.html", add_csrf(request, posts=posts, pk=thread_pk))
            return render_to_response("../templates/alumni/thread.html", add_csrf(request, posts=posts, pk=thread_pk))
    else:
        thread_form = ThreadForm()
        post_form = PostForm()
    #url_path = '../templates/alumni/newthread'+ forum.pk +'.html'
    return render(request, '../templates/alumni/newthread.html', {'thread_form': thread_form, 'post_form': post_form})
    #return HttpResponse("Hello, world. You're at the alumni index.")
    # return render(request, url_path, {'thread_form': thread_form, 'post_form': post_form})

# Django's CreateView, ListView, UpdateView and DeleteView should be used for posting new threads, comments, etc...
# these use 'default' names for their html templates 
# http://riceball.com/d/content/django-18-minimal-application-using-generic-class-based-views
# e.g. a list view will be something like templates/alumni/forum_list.html (templates/appname/model_list.html)

def spam_those_poor_suckers(subject, message, from_email = None, suckers = None):
    # a function to send mass emails to users
    # see https://docs.djangoproject.com/en/1.8/ref/contrib/auth/ for email_user()  
    if from_email is None:
        from_email = r'unreachable@dontbother.com'
    if suckers is None:
        suckers = models.User.objects.all()
    # make a list of emails from 'suckers' (i.e. recipient_list)
    recipients = []
    for spamee in suckers:
        recipients.append(spamee.email)
        spamee.email_user(subject, message)
    '''
    print recipients, type(recipients)
    # send_mass_mail(datatuple, fail_silently=False, auth_user=None, auth_password=None, connection=None)
    # datatuple is a tuple in which each element is in this format: (subject, message, from_email, recipient_list)
    datatuple = (subject, message, from_email, recipients)
    send_mass_mail(datatuple)
    '''
# display the editProfile form of some user Y to some user X. User X can 'suggest' what the field values should be
# user Y gets a email with the suggested edits and is invited to go update their profile 
# could (somehow) possible give user Y option to approve changes instead of having them edit it manually? ...
def send_proxy_info(request, editee_id):
    # editee - i.e. receiver of the edits
    editee = User.objects.get(pk=editee_id)
    editee_profile = models.Profile.objects.get(user_id=editee_id)
    name = editee.first_name
    surname = editee.last_name
    email = editee.email
    city = editee_profile.city
    country = editee_profile.country
    degree = editee_profile.degree
    grad_year = editee_profile.grad_year
    edit_form = EditProfileForm(request.POST or None, initial={'name' : name, 'surname' : surname, 'email' : email, 'city': city, "country": country, "degree" : degree, "grad_year": grad_year})

    if request.method == "POST":
        if edit_form.is_valid():

            editee.name = request.POST['first_name']
            editee.surname = request.POST['surname']
            editee.email = request.POST['email']
            editee_profile.city = request.POST['city']
            editee_profile.country = request.POST['country']
            editee_profile.degree = request.POST['degree']
            editee_profile.grad_year = request.POST['grad_year']
            # DO NOT SAVE THE EDITED FORM, SEND THE FORM AS AN EMAIL to user X
            
            # only email a user about changes if there are actually changes to begin with!
            if edit_form.has_changed():
                message = str(request.user.first_name) + " " + str(request.user.last_name) + " has suggested the following changes to your profile: " + '\n\r'
                for field in edit_form.changed_data:
                    message += field + edit_form[field] + '\n\r'
                spam_those_poor_suckers("Suggested edits to your Profile!", message, from_email = None, suckers = [editee] )
            
            # for now redirect to the same place as edit_progile would i.e. user Y's detials
            # may also want to give user X a notification that user Y will get an email !
            # this could change to go back to 'search listing' however 
            return HttpResponseRedirect('%s'%(reverse('profile')), context = {"form" : edit_form})

    return render(request, '../templates/alumni/editProfile.html', context)


# url(r'^profile/$', views.create_profile, name='create_profile')
def create_profile(request):  #create profile
    user = request.user
    prof_form = ProfileForm()
    if request.method == "POST":
        prof_form = ProfileForm(request.POST)
        profile = Profile(city = request.POST.get("city"), country = request.POST.get("country"),
                    degree = request.POST.get("degree"), grad_year = request.POST.get("grad_year"),
                    user_id = user.id)
        profile.save()
        #send email
        #email = EmailMessage('Hello', 'World', to=[ user.email])
        #email.send()
        user_info = Profile.objects.get(user_id=user.id)
        name = user.first_name
        surname = user.last_name
        email = user.email
        city = user_info.city
        country = user_info.country
        degree = user_info.degree
        grad_year = user_info.grad_year
        search = SearchForm()
        #send_email(user.email, "Test", "Hello world")
        return render(request, '../templates/alumni/profile.html', {'id': user_info.id, 'search': search, 'name' : name, 'surname' : surname, 'email' : email, 'city': city, "country": country, "degree" : degree, "grad_year": grad_year} )
    else:
        prof_form = ProfileForm()
        search = SearchForm()
        return render(request, '../templates/alumni/createProfile.html', {'form': prof_form, 'search' : search})

def profile(request):   #view profile info
    #prof = Profile.objects.get(pk=id)
    user = request.user
    #if Profile.objects.get( user_id =user.id):
    if request.method == "POST" and request.POST.get("saveProf"):   #saving profile to the database
        user = request.user
        #prof = EditProfileForm(request.POST)
        city = request.POST['city']
        country = request.POST['country']
        degree = request.POST['degree']
        grad_year = request.POST['grad_year']
        #user_name = request.POST['first_name']
        #user_lastname = request.POST['last_name']
        #user_email = request.POST['email']
        prof = Profile.objects.get(user_id =user.id)
        prof.degree = degree
        prof.grad_year = grad_year
        prof.city = city
        prof.country = country
        #profile = Profile(degree = degree, grad_year = grad_year, city = city, country = country)
        #user.first_name = user_name
        #user.last_name = user_lastname
        #user.email = user_email
        #user.save()
        prof.save()
        return render(request, '../templates/alumni/profile.html', {'id' : prof.id, 'grad_year':grad_year, 'degree':degree, \
                                                                          'city':city, 'country': country} )
    elif request.method == "POST" and request.POST.get('saveedit'):
        user = request.user
        editprof = EditProfileForm(request.POST)
        city = request.POST['city']
        country = request.POST['country']
        degree = request.POST['degree']
        grad_year = request.POST['grad_year']
        user_name = request.POST['first_name']
        user_lastname = request.POST['last_name']
        user_email = request.POST['email']
        prof = Profile.objects.get(user_id =user.id)
        prof.degree = degree
        prof.grad_year = grad_year
        prof.city = city
        prof.country = country
        #profile = Profile(degree = degree, grad_year = grad_year, city = city, country = country)
        user.first_name = user_name
        user.last_name = user_lastname
        user.email = user_email
        user.save()
        prof.save()
        return render(request, '../templates/alumni/profile.html', {'id' : prof.id, 'name':user_name, 'surname' : user_lastname,'email':user_email, 'grad_year':grad_year, 'degree':degree, \
                                                                          'city':city, 'country': country} )
    else:
        try:
            user = request.user
            user_info = Profile.objects.get( user_id =user.id)   #retrieving user profile from the database
            name = user.first_name
            surname = user.last_name
            email = user.email
            city = user_info.city
            country = user_info.country
            degree = user_info.degree
            grad_year = user_info.grad_year
            search = SearchForm()

            #job_info.append(Job.objects.get(job_profile = user.id))


            return render(request, '../templates/alumni/profile.html', {'id' : user_info.id, 'search' : search, 'name' : name, 'surname' : surname, 'email' : email,\
                                                                        'city': city, "country": country, "degree" : degree, \
                                                                        "grad_year": grad_year} )
        except:          #displaying form to create profile if user has no profile
            prof_form = ProfileForm()
            search = SearchForm()
            return render(request, '../templates/alumni/createProfile.html', {'form': prof_form, 'search' : search})

def view_profile(request): # view profile info
    user = request.user
    prof_form = ProfileForm()
    if request.method == "POST":
        prof_form = ProfileForm(request.POST)
        # create the profile
        profile = Profile(city = request.POST.get("city"), country = request.POST.get("country"),
                    degree = request.POST.get("degree"), grad_year = request.POST.get("grad_year"),
                          user_id = user.id )
        profile.save()
        user_info = Profile.objects.get(user_id=user.id)
        name = user.first_name
        surname = user.last_name
        email = user.email
        city = user_info.city
        country = user_info.country
        degree = user_info.degree
        grad_year = user_info.grad_year
        search = SearchForm()
        return render(request, '../templates/alumni/profile.html', {'id': user_info.id, 'search': search, 'name' : name, 'surname' : surname, 'email' : email, \
                                                                    'city': city, "country": country, "degree" : degree,\
                                                                    "grad_year": grad_year} )
    else:
        # view the profile
        prof_form = ProfileForm()
        search = SearchForm()
        return render(request, '../templates/alumni/createProfile.html', {'search': search, 'form': prof_form})


def spam_those_poor_suckers(subject, message, from_email = None, suckers = None):
    # a function to send mass emails to users
    # see https://docs.djangoproject.com/en/1.8/ref/contrib/auth/ for email_user()
    if from_email is None:
        from_email = r'unreachable@dontbother.com'
    if suckers is None:
        suckers = models.User.objects.all()
    # make a list of emails from 'suckers' (i.e. recipient_list)
    recipients = []
    for spamee in suckers:
        recipients.append(spamee.email)
        spamee.email_user(subject, message)
    '''
    print recipients, type(recipients)
    # send_mass_mail(datatuple, fail_silently=False, auth_user=None, auth_password=None, connection=None)
    # datatuple is a tuple in which each element is in this format: (subject, message, from_email, recipient_list)
    datatuple = (subject, message, from_email, recipients)
    send_mass_mail(datatuple)
    '''


def edit_profile(request, id):    #editing user profile
    if request.method == "POST" and request.POST.get('edit'):
        profile = Profile.objects.get(pk=id)
        user = request.user
        prof = EditProfileForm(initial={'first_name' : user.first_name, 'last_name' : user.last_name,\
                                        'email' : user.email, 'city': profile.city, "country": profile.country,\
                                        "degree" : profile.degree, "grad_year": profile.grad_year})
        return render(request, '../templates/alumni/editProfile.html', {'form' : prof})
    elif request.method == "POST" and request.POST.get('saveedit'):   #saving edits to the database
        user = request.user
        editprof = EditProfileForm(request.POST)
        city = request.POST['city']
        country = request.POST['country']
        degree = request.POST['degree']
        grad_year = request.POST['grad_year']
        user_name = request.POST['first_name']
        user_lastname = request.POST['last_name']
        user_email = request.POST['email']
        prof = Profile.objects.get(pk=id)
        prof.degree = degree
        prof.grad_year = grad_year
        prof.city = city
        prof.country = country
        user.first_name = user_name
        user.last_name = user_lastname
        user.email = user_email
        user.save()
        prof.save()
        return render(request, '../templates/alumni/profile.html', {'name':user_name, 'surname' : user_lastname,'email':user_email, 'grad_year':grad_year, 'degree':degree, \
                                                                          'city':city, 'country': country} )

def log_in(request):
    log_in = LoginForm()
    if request.method == "POST" and request.POST.get('login'):  #logging in an already signed up user
        log_in = LoginForm(request.POST)
        email = request.POST['email']
        password = request.POST['password']
        userid = models.User.objects.get(email=email)
        #userid = models.User.objects.filter(email=email)[0]
        username = userid.id
        user = authenticate(username=username, password=password)
        #user = authenticate(email=email, password=password)
        login(request, user)
        return render(request,'../templates/alumni/homepage.html', {'username' : username})
    elif request.method == "POST" and request.POST.get('newUser'): # and request.POST.get("type"):  #creating a new user
        form = UserForm(request.POST)
        if form.is_valid():
            cursor = connection.cursor()
            cursor.execute('SELECT COUNT(*) FROM auth_user')
            num = cursor.fetchall()
            username = num[0][0] +1
            #new_user = x
            new_user = User.objects.create_user(**form.cleaned_data)
            username = username
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            login(request, user)
            return render(request, "../templates/alumni/toProfile.html", {'userid' : new_user.id})
    elif request.method == "GET":   #displaying the log in and sign up forms
        logout(request)
        log_in = LoginForm()
        sign_up = UserForm()
        return render(request, '../templates/alumni/login.html', {'form':log_in, 'signupForm' : sign_up})

def home(request):
    search = SearchForm()
    num_items = 3
    new_events = models.Event.objects.all().order_by('-created_date')[:num_items]
    new_adverts = models.Advert.objects.all().order_by('-created_date')[:num_items]
    # posts = models.Posts.objects.all().order_by('created_date')[:num_items]
    new_events = make_paginator(request, new_events, 20)
    new_adverts = make_paginator(request, new_adverts, 20)
    #posts = make_paginator(request, posts, 20)
    return render(request, '../templates/alumni/homepage.html', {'search': search,'events':new_events, 'adverts' : new_adverts, 'test' : ['HTML','REALLY','SUCKS']})
    # add_csrf(
    # return render_to_response('../templates/alumni/homepage.html', add_csrf(request, 'context_events' = new_events, 'context_adverts' = new_adverts))

def create_events(request):  #create events
    if request.method == "POST":
        user = request.user
        events = EventsForm(request.POST)
        title = request.POST['title']
        event_type = request.POST['event_type']
        description = request.POST['description']
        year = request.POST['year']
        month = request.POST['month']
        day = request.POST['day']
        street = request.POST['street']
        city = request.POST['city']
        country = request.POST['country']
        event = models.Event(creating_user = user, title = title, event_type = event_type, description = description, \
                      year = year, month = month, day = day, street = street, city = city, country = country)
        event.save()
        spam_those_poor_suckers(title, "Event Description: " + description+ "\n Date: " + day+"-"+month+"-"+year +\
                                "\n Address: " + street + ", "+city + ", " + country + "\n RSVP: " +user.email, from_email = 'csalumniuct@gmail.com', \
                                suckers = None)
        search = SearchForm()
        return render(request, '../templates/alumni/display_event.html', {'creating_user': user.email, 'search': search, 'id' : event.id, 'title':title, 'event_type':event_type, \
                                                                          'description':description, 'year': year, \
                                                                        'month':month, 'day':day, 'street':street,\
                                                                          'city':city, 'country':country})
    else:   #form to create an event
        events = EventsForm()
        search = SearchForm()
        return render(request, '../templates/alumni/create_event.html', {'search': search, 'form':events})


def events(request):  #display events
    search = SearchForm()
    if request.method == "POST" and request.POST.get('delete'):
        obj = models.Event.objects.get(pk=id)
        #if request.user == obj.creating_user:  delete only if creating user
        obj.delete()
        event = Event.objects.all()
        return render(request, '../templates/alumni/events.html', { 'search': search, 'events': event})
    else:
        event = Event.objects.all()
        return render(request, '../templates/alumni/events.html', {'search': search, 'events':event})


def events_view(request, id):   #view selected event
    search = SearchForm()
    event = Event.objects.get(pk=id)
    title = event.title
    event_type = event.event_type
    description = event.description
    year = event.year
    month = event.month
    day = event.month
    street = event.street
    city = event.street
    country = event.country
    user = event.creating_user
    return render(request, '../templates/alumni/display_event.html', {'creating_user': user.email,'search' : search, 'id' : event.id, 'title':title,\
                                                                      'event_type':event_type,  'description':description,\
                                                                      'year': year,'month':month, 'day':day,\
                                                                      'street':street, 'city':city, 'country':country})

def events_delete(request, id):
    search = SearchForm()
    if request.method == "POST" and request.POST.get('delete'):  #deleting event
        obj = Event.objects.get(pk=id)
        if request.user == obj.creating_user:
            obj.delete()
            event = Event.objects.all()
            return render(request, '../templates/alumni/events.html', {'search': search, 'events': event})
    else:
        event = Event.objects.all()    #displaying event
        return render(request, '../templates/alumni/events.html', {'search': search, 'events':event})

def events_edit(request, id):    #editing an event
    search = SearchForm()
    if request.method == "POST" and request.POST.get('edit'):  #displaying edit event form
        event = Event.objects.get(pk=id)
        event = EventsForm(initial={'search': search, 'title' : event.title, 'event type' : event.event_type,\
                                    'description' : event.description,  'year' : event.year, 'month' : event.month, \
                                    'day' : event.day, 'street' : event.street, 'city' : event.city, \
                                    'country' : event.country})
        return render(request, '../templates/alumni/edit_event.html', {'form' : event, 'search':search})
    elif request.method == "POST" and request.POST.get('save'):  #saving the form to the database
        user = request.user
        events = EventsForm(request.POST)
        title = request.POST['title']
        event_type = request.POST['event_type']
        description = request.POST['description']
        year = request.POST['year']
        month = request.POST['month']
        day = request.POST['day']
        street = request.POST['street']
        city = request.POST['city']
        country = request.POST['country']
        event_del = Event.objects.get(pk=id)
        event_del.delete()
        event = models.Event(creating_user = user, title = title, event_type = event_type, description = description, \
                      year = year, month = month, day = day, street = street, city = city, country = country)
        event.save()
        return render(request, '../templates/alumni/display_event.html', {'creating_user': user.email, 'search': search, 'id' : event.id, 'title':title,\
                                                                          'event_type':event_type, 'description':description, \
                                                                          'year': year, 'month':month, 'day':day, \
                                                                          'street':street,'city':city, 'country':country})


def job_history(request):
    user = request.user
    job_form = JobForm()
    search = SearchForm()
    if request.method == "POST" and request.POST.get("saveJob"):   #saving a newly created job
        job_form = JobForm(request.POST)
        jobs = Job(job_profile = user.id, company_name = request.POST.get("company_name"), job_desc = request.POST.get("job_desc"),
                    job_title = request.POST.get("job_title"), start_date = request.POST.get("start_date"),
                    end_date = request.POST.get("end_date"), job_location = request.POST.get("location") )
        jobs.save()
        name = user.first_name
        surname = user.last_name
        email = user.email
        return render(request, '../templates/alumni/newjob.html', {'id': user.id, 'search': search, 'name' : name, 'surname' : surname,\
                                                                  'email' : email, 'company_name' : request.POST.get("company_name"),\
                                                                  'job_desc': request.POST.get("job_desc"), \
                                                                  "job_title": request.POST.get("job_title"),\
                                                                  'location' : request.POST.get("location"), \
                                                                  "start_date" : request.POST.get("start_date"),\
                                                                  "end_date": request.POST.get("end_date")} )
    elif request.method == "POST" and request.POST.get("jobs"):   #a user can view their own job history
        job_info = Job.objects.all()
        jobs = []
        user = request.user
        user_info = Profile.objects.get(user_id=user.id)
        for i in job_info:
            if str(i.job_profile) == str(user_info.id):
                jobs.append(i)
        return render(request, '../templates/alumni/jobs.html', {'search' : search, 'jobs':jobs })
    else:
    #if request.method == "GET":       #form to add new jobs
        job_form = JobForm()
        return render(request, '../templates/alumni/createJobs.html', {'form': job_form, 'search' : search})

def job_view(request, id):
    job = Job.objects.get(pk=id)
    search = SearchForm()
    return render(request, '../templates/alumni/display_job.html', { 'search': search, 'job': job} )


def job_delete(request, id):   #not working properly
    search = SearchForm()
    if request.method == "POST" and request.POST.get('delete'):  #deleting event
        user = request.user
        user_info = Profile.objects.get(user_id=user.id)
        obj = Job.objects.get(pk=id)
        obj.delete()
        jobs = []
        job_info = Job.objects.all()
        for i in job_info:
            if str(i.job_profile) == str(user_info.id):  #not displaying events after delete
                jobs.append(i)
        return render(request, '../templates/alumni/jobs.html', {'search' : search, 'jobs':jobs })
    else:
        user = request.user
        user_info = Profile.objects.get(user_id=user.id)
        jobs = []
        job_info = Job.objects.all()
        for i in job_info:
            if str(i.job_profile) == str(user_info.id):
                jobs.append(i)
        return render(request, '../templates/alumni/jobs.html', {'search' : search, 'job':jobs })


def job_edit(request, id):    #editing a job -- finish this
    search = SearchForm()
    if request.method == "POST" and request.POST.get('edit'):  #displaying edit event form
        job = Job.objects.get(pk=id)
        job = JobForm(initial={'search': search, 'job_title' : job.job_title, 'job_desc' : job.job_desc,\
                                    'company_name' : job.company_name,  'location' : job.job_location, 'start_date' : job.start_date, \
                                    'end_date' : job.end_date})
        return render(request, '../templates/alumni/edit_job.html', {'form' : job})
    elif request.method == "POST" and request.POST.get('savejobedit'):  #saving the form to the database
        user = request.user
        job = Job.objects.get(pk = id)
        job.company_name = request.POST['company_name']
        job.job_desc = request.POST['job_desc']
        job.job_title = request.POST['job_title']
        job.job_location = request.POST['location']
        job.start_date = request.POST['start_date']
        job.end_date = request.POST['end_date']
        job.save()
        return render(request, '../templates/alumni/display_job.html', { 'search': search,'job': job} )


def view_other_user(request, id):
    #if request.GET['search_item'] != "JOB":  #display user and profile info
    search = SearchForm()
    user = User.objects.get(pk=id)
    profile = Profile.objects.get(pk=id)
    return render(request, '../templates/alumni/search_item.html', {'search' : search, 'user': user, 'profile':profile})
    ''' else:
        job = Advert.objects.get(pk=id)
        return render(request, '../templates/alumni/search_job.html', {'search' : search,  'job':job})'''
