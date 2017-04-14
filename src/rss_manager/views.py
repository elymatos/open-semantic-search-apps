from django.shortcuts import render
from django.shortcuts import render
from django.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.template import RequestContext
from django.views import generic
from django.forms import ModelForm
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone


import datetime
from datetime import timedelta

from etl.tasks import index_rss

from models import RSS_Feed


class RSSFeedForm(ModelForm):

	class Meta:
		model = RSS_Feed
		fields = '__all__'

class IndexView(generic.ListView):
	model = RSS_Feed

class DetailView(generic.DetailView):
	model = RSS_Feed

class CreateView(generic.CreateView):
	model = RSS_Feed

class UpdateView(generic.UpdateView):
	model = RSS_Feed


#
# New/additional feed
#

def create_feed(request):

	if request.method == 'POST':

		form = RSSFeedForm(request.POST, request.FILES)


		if form.is_valid():
			print "form valid"
			feed = form.save()

			return HttpResponseRedirect( reverse('rss_manager:detail', args=[feed.pk]) ) # Redirect after POST

	else:
		form = RSSFeedForm()

	return render_to_response('rss_manager/rss_feed_form.html', 
			{'form': form,	}, context_instance=RequestContext(request) )
	

#
# Updated an feed
#

def update_feed(request, pk):

	feed = RSS_Feed.objects.get(pk=pk)
	
	if request.POST:
		
		form = RSSFeedForm(request.POST, request.FILES, instance=feed)
		
		if form.is_valid():
			form.save()

			return HttpResponseRedirect( reverse('rss_manager:detail', args=[pk])) # Redirect after POST
		
			pass
	else:
		form = RSSFeedForm(instance=feed)

	return render_to_response('rss_manager/rss_feed_form.html', 
			{'form': form, 'feed': feed }, context_instance=RequestContext(request) )


#
# Add feed to queue
# So a worker will download/read the feed and import/download all new articles
#

def import_feed(request, pk):

	feed = RSS_Feed.objects.get(pk=pk)
	
	# add to queue
	last_imported = datetime.datetime.now()
	index_rss.delay(uri=feed.uri)

	# save new timestamp
	feed.last_imported = last_imported
	feed.save()

	
	return render(request, 'rss_manager/rss_feed_import.html', {'id': pk,})


#
# Add all feeds to queue where last import was before configured delta time of the feed
#

def import_feeds(request):

	verbose = True

	log = []
	count = 0
	count_queued = 0

	for feed in RSS_Feed.objects.all():

		count += 1

		if verbose:
			log.append( "Checking delta time of feed: {}".format(feed) ) 


		add_to_queue = True


		# If delta time, do not import this feed within this time by setting add_to_queue to false
		if feed.delta and feed.last_imported:

			# when next import allowed (because time delta passed)?
			next_import = feed.last_imported + timedelta(minutes=feed.delta)

			# don't check time delta if last import in future (i.e. if system time was wrong)
			if feed.last_imported < timezone.now():			

				# if time for next import not reached, do not index
				if timezone.now() < next_import:
					add_to_queue = False

			if verbose:
				log.append( "Last import: {}".format(feed.last_imported) )
				log.append( "Next import: {}".format(next_import) ) 


		if add_to_queue:
			
			if verbose:
				log.append( "Adding feed to queue: {}".format(feed) ) 

			# add to queue
			last_imported = datetime.datetime.now()
			index_rss.delay(uri=feed.uri)

			# save new timestamp
			feed.last_imported = last_imported
			feed.save()

			count_queued += 1
	
	#
 	# stats / log
 	#
 	
	response = "Feeds to queue: {} of {}".format(count_queued, count)

	if len(log) > 0:
		response += "\n\n" + "\n".join(log)
	
	#
	# return response
	#
	
	status = HttpResponse(response)
	status["Content-Type"] = "text/plain" 
	return status