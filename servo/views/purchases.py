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

import gsxws

from django.forms.models import modelform_factory
from django.forms.models import inlineformset_factory

from django.utils.translation import ugettext as _

from django.shortcuts import render, redirect
from servo.models.order import ServiceOrderItem
from django.contrib.auth.decorators import permission_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.contrib import messages

from servo.models import Product, GsxAccount, PurchaseOrder, PurchaseOrderItem
from servo.forms import PurchaseOrderItemEditForm, PurchaseOrderSearchForm


@permission_required("servo.change_purchaseorder")
def list_pos(request):
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Sum

    now = timezone.now()
    data = {'title': _("Purchase Orders")}

    initial = {'start_date': now - timedelta(days=30), 'end_date': now}
    all_orders = PurchaseOrder.objects.filter(
        created_at__range=(initial['start_date'], initial['end_date'])
    )

    form = PurchaseOrderSearchForm(initial=initial)

    if request.method == 'POST':
        all_orders = PurchaseOrder.objects.all()
        form = PurchaseOrderSearchForm(request.POST, initial=initial)

        if form.is_valid():
            fdata = form.cleaned_data
            reference = fdata.get('reference')
            if reference:
                all_orders = all_orders.filter(reference__contains=reference)
            if fdata.get('state') == 'open':
                all_orders = all_orders.filter(submitted_at=None)
            if fdata.get('state') == 'submitted':
                all_orders = all_orders.exclude(submitted_at=None)
            if fdata.get('state') == 'received':
                all_orders = all_orders.exclude(has_arrived=True)
            s, e = (fdata.get('start_date'), fdata.get('end_date'))
            if s and e:
                all_orders = all_orders.filter(created_at__range=(s, e))
            created_by = fdata.get('created_by')
            if created_by:
                all_orders = all_orders.filter(created_by=created_by)

    page = request.GET.get("page")
    paginator = Paginator(all_orders, 50)

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    data['orders'] = orders
    data['form'] = form
    data['total'] = all_orders.aggregate(Sum('total'))
    return render(request, "purchases/list_pos.html", data)


@permission_required("servo.change_purchaseorder")
def delete_from_po(request, pk, item_id):
    # @TODO - decrement amount_ordered?
    po = PurchaseOrder.objects.get(pk=pk)
    poi = PurchaseOrderItem.objects.get(pk=item_id)
    poi.delete()
    messages.success(request, _(u'Product %s removed' % poi.product.code))
    return redirect(po)


@permission_required("servo.change_purchaseorder")
def add_to_po(request, pk, product_id):
    po = PurchaseOrder.objects.get(pk=pk)
    product = Product.objects.get(pk=product_id)
    po.add_product(product, 1, request.user)
    messages.success(request, _(u"Product %s added" % product.code))
    return redirect(edit_po, po.pk)


def view_po(request, pk):
    po = PurchaseOrder.objects.get(pk=pk)
    title = _('Purchase Order %d' % po.pk)
    return render(request, "purchases/view_po.html", locals())


@permission_required("servo.change_purchaseorder")
def edit_po(request, pk, item_id=None):

    if pk is not None:
        po = PurchaseOrder.objects.get(pk=pk)
    else:
        po = PurchaseOrder(created_by=request.user)

    PurchaseOrderForm = modelform_factory(PurchaseOrder, exclude=[])
    form = PurchaseOrderForm(instance=po)

    ItemFormset = inlineformset_factory(
        PurchaseOrder,
        PurchaseOrderItem,
        extra=0,
        form=PurchaseOrderItemEditForm,
        exclude=[]
    )

    formset = ItemFormset(instance=po)

    if request.method == "POST":

        form = PurchaseOrderForm(request.POST, instance=po)

        if form.is_valid():

            po = form.save()
            formset = ItemFormset(request.POST, instance=po)

            if formset.is_valid():

                formset.save()
                msg = _("Purchase Order %d saved" % po.pk)

                if "confirm" in request.POST.keys():
                    po.submit(request.user)
                    msg = _("Purchase Order %d submitted") % po.pk

                messages.success(request, msg)
                return redirect(list_pos)

    request.session['current_po'] = po
    data = {'order': po, 'form': form}
    data['formset'] = formset
    data['title'] = _('Purchase Order #%d' % po.pk)

    return render(request, "purchases/edit_po.html", data)


@permission_required("servo.change_purchaseorder")
def order_stock(request, po_id):
    """
    Submits the PO as a GSX Stocking Order
    Using the default GSX account.
    """
    po = PurchaseOrder.objects.get(pk=po_id)

    if request.method == "POST":
        if po.submitted_at:
            messages.error(request, _(u'Purchase Order %s has already been submitted') % po.pk)
            return list_pos(request)

        act = GsxAccount.default(request.user)

        stock_order = gsxws.StockingOrder(
            shipToCode=act.ship_to,
            purchaseOrderNumber=po.id
        )

        for i in po.purchaseorderitem_set.all():
            stock_order.add_part(i.code, i.amount)

        try:
            result = stock_order.submit()
            po.supplier = "Apple"
            po.confirmation = result.confirmationNumber
            po.submit(request.user)
            msg = _("Products ordered with confirmation %s" % po.confirmation)
            messages.success(request, msg)
        except gsxws.GsxError, e:
            messages.error(request, e)

        return redirect(list_pos)

    data = {'action': request.path}
    return render(request, "purchases/order_stock.html", data)


@permission_required('servo.delete_purchaseorder')
def delete_po(request, po_id):
    po = PurchaseOrder.objects.get(pk=po_id)
    try:
        po.delete()
        messages.success(request, _("Purchase Order %s deleted" % po_id))
    except Exception, e:
        messages.error(request, e)
    return redirect(list_pos)


@permission_required('servo.add_purchaseorder')
def create_po(request, product_id=None, order_id=None):
    po = PurchaseOrder(created_by=request.user)
    location = request.user.get_location()
    po.location = location
    po.save()

    if order_id is not None:
        po.sales_order_id = order_id
        for i in ServiceOrderItem.objects.filter(order_id=order_id):
            po.add_product(i, amount=1, user=request.user)

    if product_id is not None:
        product = Product.objects.get(pk=product_id)
        po.add_product(product, amount=1, user=request.user)

    messages.success(request, _("Purchase Order %d created" % po.pk))

    return redirect(edit_po, po.pk)
