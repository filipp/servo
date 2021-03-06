# -*- coding: utf-8 -*-
# Copyright (c) 2013, First Party Software
# All rights reserved.

# Redistribution and use in source and binary forms, with or without modification, 
# are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, 
# this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice, 
# this list of conditions and the following disclaimer in the documentation 
# and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE 
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT 
# OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF 
# SUCH DAMAGE.

from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView, TemplateView
from servo.views import account, files, gsx

urlpatterns = patterns(
    '',
    url(r'^$', RedirectView.as_view(url="orders/", permanent=False), name="home"),

    url(r'^checkin/', include('servo.urls.checkin')),
    url(r'^orders/', include('servo.urls.order')),
    url(r'^repairs/', include('servo.urls.repairs')),
    url(r'^customers/', include('servo.urls.customer')),
    url(r'^devices/', include('servo.urls.device')),
    url(r'^admin/', include('servo.urls.admin')),

    url(r'^stats/', include('servo.urls.stats')),

    url(r'^notes/', include('servo.urls.note')),
    url(r'^sales/', include('servo.urls.sales')),

    url(r'^queues/(\d+)/statuses/$', 'servo.views.queue.statuses'),

    url(r'^barcode/([\w\-]+)/$', 'servo.views.note.show_barcode', name='barcodes-view'),
    url(r'^files/(?P<pk>\d+)/view/$', files.view_file),
    url(r'^files/(?P<path>.+)/$', files.get_file),

    url(r'^login/$', account.login, name="accounts-login"),
    url(r'^logout/$', account.logout, name="accounts-logout"),
    #url(r'^register/$', account.register, name="accounts-register"),

    url(r'^about/$', TemplateView.as_view(template_name="about.html")),

    url(r'^repairs/(\d+)/parts/(\d+)/return_label/$', gsx.return_label,
        name="parts-return_label"),
    url(r'^repairs/([A-Z0-9]+)/details/$', gsx.repair_details, name="repairs-get_details"),
    url(r'^returns/part/(?P<part_id>\d+)/register_return/$', gsx.register_return,
        name='parts-register_return'),

    url(r'^events/(\d+)/ack/', 'servo.views.events.acknowledge', name="events-ack_event"),
    url(r'^tags/(\d+)/clear/', 'servo.views.tags.clear', name="tags-clear"),

    (r'^api/', include('servo.urls.api')),
    (r'^kaboom/$', 'servo.views.error.report'),
    
    url(r'^(?P<username>[\w@\+\-\._]+)/', include('servo.urls.account')),

)
