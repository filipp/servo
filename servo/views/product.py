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

import json
from decimal import *

from django.db.models import Q
from django.db import IntegrityError

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _
from django.forms.models import inlineformset_factory
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import permission_required

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from servo.models import (Attachment, TaggedItem,
                          Product, ProductCategory,
                          Inventory, Location, inventory_totals,
                          GsxAccount)
from servo.forms.product import ProductForm, CategoryForm, ProductSearchForm


def prep_list_view(request, group='all'):
    """
    Prepares the product list view
    """
    title = _("Products")
    all_products = Product.objects.all()
    categories = ProductCategory.objects.all()

    if group == 'all':
        group = ProductCategory(title=_('All'), slug='all')
    else:
        group = categories.get(slug=group)
        all_products = group.get_products()

    if request.method == 'POST':
        form = ProductSearchForm(request.POST)
        if form.is_valid():
            fdata = form.cleaned_data

            description = fdata.get('description')
            if description:
                all_products = all_products.filter(description__icontains=description)

            title = fdata.get('title')
            if title:
                all_products = all_products.filter(title__icontains=title)

            code = fdata.get('code')
            if code:
                all_products = all_products.filter(code__icontains=code)

            tag = fdata.get('tag')
            if tag:
                tag = tag.tag
                title += u" / %s" % tag
                all_products = all_products.filter(tags__tag=tag)
    else:
        form = ProductSearchForm()

    title += u" / %s" % group.title
    page = request.GET.get("page")
    paginator = Paginator(all_products.distinct(), 25)

    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    return locals()


def tags(request):
    """
    Returns all product tags
    """
    tags = TaggedItem.objects.filter(content_type__model="product")
    tags = tags.distinct("tag").values_list("tag", flat=True)
    return HttpResponse(json.dumps(list(tags)), content_type='application/json')


def list_products(request, group='all'):
    data = prep_list_view(request, group)
    p, s = inventory_totals()
    data['total_sales_value'] = s
    data['total_purchase_value'] = p

    return render(request, "products/index.html", data)


@permission_required("servo.change_product")
def upload_gsx_parts(request, group=None):
    from servo.forms.product import PartsImportForm
    form = PartsImportForm()

    data = {'action': request.path}

    if request.method == "POST":

        form = PartsImportForm(request.POST, request.FILES)

        if form.is_valid():
            data = form.cleaned_data
            filename = "servo/uploads/products/partsdb.csv"
            destination = open(filename, "wb+")

            for chunk in data['partsdb'].chunks():
                destination.write(chunk)

            messages.success(request, _("Parts database uploaded for processing"))
            return redirect(list_products)

    data['form'] = form
    return render(request, "products/upload_gsx_parts.html", data)


@permission_required("servo.change_product")
def download_products(request, group="all"):
    filename = "products"

    if group == "all":
        products = Product.objects.all()
    else:
        category = ProductCategory.objects.get(slug=group)
        products = category.get_products()
        filename = group

    response = HttpResponse(content_type="text/plain; charset=utf-8")
    response['Content-Disposition'] = 'attachment; filename="%s.txt"' % filename

    response.write(u"ID\tCODE\tTITLE\tPURCHASE_PRICE\tSALES_PRICE\tSTOCKED\n")

    for p in products:
        row = u"%s\t%s\t%s\t%s\t%s\t%s\n" % (p.pk,
                                             p.code,
                                             p.title,
                                             p.price_purchase_stock,
                                             p.price_sales_stock, 0)
        response.write(row)

    return response


@permission_required("servo.change_product")
def upload_products(request, group=None):
    """"
    Format should be the same as from download_products
    """
    import io
    from servo.forms import ProductUploadForm
    location = request.user.get_location()
    form = ProductUploadForm()

    if request.method == "POST":
        form = ProductUploadForm(request.POST, request.FILES)

        if form.is_valid():
            string = u''
            category = form.cleaned_data['category']
            data = form.cleaned_data['datafile'].read()

            for i in ('utf-8', 'latin-1',):
                try:
                    string = data.decode(i)
                except:
                    pass

            if not string:
                raise ValueError(_('Unsupported file encoding'))

            i = 0
            sio = io.StringIO(string, newline=None)

            for l in sio.readlines():
                cols = l.strip().split("\t")

                if cols[0] == "ID":
                    continue # Skip header row

                if len(cols) < 2:
                    continue # Skip empty rows

                if len(cols) < 6:  # No ID row, pad it
                    cols.insert(0, "")

                product, created = Product.objects.get_or_create(code=cols[1])

                product.title = cols[2].strip(' "').replace('""', '"') # Remove Excel escapes
                product.price_purchase_stock = cols[3].replace(',', '.')
                product.price_sales_stock = cols[4].replace(',', '.')
                product.save()

                if category:
                    product.categories.add(category)

                inventory, created = Inventory.objects.get_or_create(
                    product=product, location=location
                )
                inventory.amount_stocked = cols[5]
                inventory.save()
                i += 1

            messages.success(request, _(u"%d products imported") % i)

            return redirect(list_products)

    action = request.path
    title = _("Upload products")
    return render(request, "products/upload_products.html", locals())


@permission_required("servo.change_product")
def edit_product(request, pk=None, code=None, group='all'):

    initial = {}
    product = Product()

    data = prep_list_view(request, group)

    if pk is not None:
        product = Product.objects.get(pk=pk)
        form = ProductForm(instance=product)

    if not group == 'all':
        cat = ProductCategory.objects.get(slug=group)
        initial = {'categories': [cat]}
        data['group'] = cat

    product.update_photo()

    if code is not None:
        product = cache.get(code)

    form = ProductForm(instance=product, initial=initial)
    InventoryFormset = inlineformset_factory(
        Product,
        Inventory,
        extra=1,
        max_num=1,
        exclude=[]
    )

    formset = InventoryFormset(
        instance=product,
        initial=[{'location': request.user.location}]
    )

    if request.method == "POST":

        form = ProductForm(request.POST, request.FILES, instance=product)

        if form.is_valid():

            product = form.save()
            content_type = ContentType.objects.get(model="product")

            for a in request.POST.getlist("attachments"):
                doc = Attachment.objects.get(pk=a)
                product.attachments.add(doc)

            tags = [x for x in request.POST.getlist('tag') if x != '']

            for t in tags:
                tag, created = TaggedItem.objects.get_or_create(
                    content_type=content_type,
                    object_id=product.pk,
                    tag=t)
                tag.save()

            formset = InventoryFormset(request.POST, instance=product)

            if formset.is_valid():
                formset.save()
                messages.success(request, _(u"Product %s saved") % product.code)
                return redirect(product)
            else:
                messages.error(request, _('Error in inventory details'))
        else:
            messages.error(request, _('Error in product info'))

    data['form'] = form
    data['product'] = product
    data['formset'] = formset
    data['title'] = product.title

    return render(request, "products/form.html", data)


@permission_required("servo.delete_product")
def delete_product(request, pk, group):
    from django.db.models import ProtectedError

    product = Product.objects.get(pk=pk)

    if request.method == 'POST':
        try:
            product.delete()
            Inventory.objects.filter(product=product).delete()
            messages.success(request, _("Product deleted"))
        except ProtectedError:
            messages.error(request, _('Cannot delete product'))

        return redirect(list_products, group)

    action = request.path
    return render(request, 'products/remove.html', locals())


def search(request):

    query = request.GET.get("q")
    request.session['search_query'] = query

    results = Product.objects.filter(
        Q(code__icontains=query) | Q(title__icontains=query) | Q(eee_code__icontains=query)
    )

    paginator = Paginator(results, 100)
    page = request.GET.get("page")

    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    title = _(u'Search results for "%s"') % query
    group = ProductCategory(title=_('All'), slug='all')

    return render(request, 'products/search.html', locals())


def view_product(request, pk=None, code=None, group=None):

    product = Product()
    inventory = Inventory.objects.none()

    try:
        product = Product.objects.get(pk=pk)
        inventory = Inventory.objects.filter(product=product)
    except Product.DoesNotExist:
        product = cache.get(code)

    data = prep_list_view(request, group)

    data['product'] = product
    data['title'] = product.title
    data['inventory'] = inventory

    return render(request, "products/view.html", data)


@permission_required("servo.change_productcategory")
def edit_category(request, slug=None, parent_slug=None):

    form = CategoryForm()
    category = ProductCategory()

    if slug is not None:
        category = ProductCategory.objects.get(slug=slug)
        form = CategoryForm(instance=category)

    if parent_slug is not None:
        parent = ProductCategory.objects.get(slug=parent_slug)
        form = CategoryForm(initial={'parent': parent.pk})

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            try:
                category = form.save()
            except IntegrityError:
                messages.error(request, _(u'Category %s already exists') % category.title)
                return redirect(list_products)
            messages.success(request, _(u"Category %s saved") % category.title)
            return redirect(category)
        else:
            messages.error(request, form.errors)
            return redirect(list_products)

    return render(request, "products/category_form.html", locals())


@permission_required("servo.delete_productcategory")
def delete_category(request, slug):

    category = ProductCategory.objects.get(slug=slug)

    if request.method == "POST":
        category.delete()
        messages.success(request, _("Category deleted"))

        return redirect(list_products)

    data = {'category': category}
    data['action'] = request.path
    return render(request, 'products/delete_category.html', data)


@permission_required("servo.change_order")
def choose_product(request, order_id, product_id=None, target_url="orders-add_product"):
    """
    order_id can be either Service Order or Purchase Order
    """
    data = {'order': order_id}
    data['action'] = request.path
    data['target_url'] = target_url

    if request.method == "POST":
        query = request.POST.get('q')

        if len(query) > 2:
            products = Product.objects.filter(
                Q(code__icontains=query) | Q(title__icontains=query)
            )
            data['products'] = products

        return render(request, 'products/choose-list.html', data)

    return render(request, 'products/choose.html', data)


def get_info(request, location, code):
    try:
        product = Product.objects.get(code=code)
        inventory = Inventory.objects.filter(product=product)
    except Product.DoesNotExist:
        product = cache.get(code)

    return render(request, 'products/get_info.html', locals())


def update_price(request, pk):
    product = Product.objects.get(pk=pk)
    try:
        GsxAccount.default(request.user)
        product.update_price()
        messages.success(request, _('Price info updated from GSX'))
    except Exception, e:
        messages.error(request, _('Failed to update price from GSX'))

    return redirect(product)
