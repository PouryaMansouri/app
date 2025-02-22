import invoice.models as invoice_models
import jdatetime
from django.db import models
from django.db.models.aggregates import Sum
from django.db.models.expressions import Value, F
from django.db.models.fields import DecimalField
from django.db.models.functions.comparison import Coalesce


class AccountingManager(models.Manager):
    def completed_user_invoices(self, user):
        statuses = invoice_models.Invoice.Statuses
        return self.filter(items__product__FK_Shop__FK_ShopManager=user,
                           status__in=[statuses.COMPLETED, statuses.CANCELED]
                           ).order_by('-created_datetime')

    def completed_user_shop_invoices(self, user, shop_slug):
        statuses = invoice_models.Invoice.Statuses
        return self.filter(items__product__FK_Shop__FK_ShopManager=user,
                           items__product__FK_Shop__Slug=shop_slug, status__in=[
                               statuses.COMPLETED, statuses.CANCELED]
                           ).order_by('-created_datetime')

    def uncompleted_user_invoices(self, user):
        statuses = invoice_models.Invoice.Statuses
        return self.filter(items__product__FK_Shop__FK_ShopManager=user,
                           status__in=[
                               statuses.AWAIT_CUSTOMER_APPROVAL, statuses.AWAIT_SHOP_CHECKOUT,
                               statuses.AWAIT_SHOP_APPROVAL, statuses.PREPATING_PRODUCT
                           ]).order_by('-created_datetime')

    def uncompleted_user_shop_invoices(self, user, shop_slug):
        statuses = invoice_models.Invoice.Statuses
        return self.filter(items__product__FK_Shop__FK_ShopManager=user,
                           items__product__FK_Shop__Slug=shop_slug, status__in=[
                               statuses.AWAIT_CUSTOMER_APPROVAL, statuses.AWAIT_SHOP_CHECKOUT,
                               statuses.AWAIT_SHOP_APPROVAL, statuses.PREPATING_PRODUCT
                           ]).order_by('-created_datetime')

    def unconfirmed_user_shop_invoices(self, user, shop_slug):
        return self.filter(items__product__FK_Shop__FK_ShopManager=user,
                           items__product__FK_Shop__Slug=shop_slug,
                           items__status=invoice_models.InvoiceItem.ItemStatuses.AWAIT_SHOP_APPROVAL
                           ).order_by('-created_datetime')

    def shop_invoices(self, shop_slug):
        return self.annotate(
            coupon_price=Coalesce(
                Sum('coupon_usages__price_applied',
                    output_field=DecimalField()), Value(0)),
            price=F('invoice_price_with_discount') +
                  F('logistic_price') -
                  F('coupon_price'),
            weight=F('total_weight_gram'),
        ).filter(items__product__FK_Shop__Slug=shop_slug).order_by('-created_datetime')


class InvoiceItemManager(models.Manager):
    def uncompleted_user_shop_factors(self, user, shop_slug):
        statuses = invoice_models.InvoiceItem.ItemStatuses
        return self.filter(product__FK_Shop__FK_ShopManager=user,
                           product__FK_Shop__Slug=shop_slug, status__in=[
                               statuses.AWAIT_CUSTOMER_APPROVAL, statuses.AWAIT_SHOP_CHECKOUT,
                               statuses.AWAIT_SHOP_APPROVAL, statuses.PREPATING_PRODUCT
                           ]).order_by('-added_datetime')

    def completed_user_shop_factors(self, user, shop_slug):
        statuses = invoice_models.InvoiceItem.ItemStatuses
        return self.filter(
            product__FK_Shop__FK_ShopManager=user,
            product__FK_Shop__Slug=shop_slug,
            status__in=[statuses.COMPLETED, statuses.CANCELED, ]).order_by(
            '-added_datetime')

    def user_total_sell(self, user):
        return self.filter(
            product__FK_Shop__FK_ShopManager=user,
            invoice__status__in=[invoice_models.Invoice.Statuses.COMPLETED]).aggregate(
            amont=Sum('product__Price'))

    def current_week_user_total_sell(self, user, shop_slug):
        now = jdatetime.datetime.now()
        current_week_start_date = now - jdatetime.timedelta(days=4)
        return self.filter(
            product__FK_Shop__FK_ShopManager=user,
            invoice__status=invoice_models.Invoice.Statuses.COMPLETED,
            product__FK_Shop__Slug=shop_slug,
            invoice__created_datetime__gt=str(
                current_week_start_date.togregorian())).aggregate(
            amont=Sum('product__Price'))

    def last_week_user_total_sell(self, user, shop_slug):
        now = jdatetime.datetime.now()
        current_week_start_date = now - jdatetime.timedelta(days=4)
        last_week_start_date = current_week_start_date - jdatetime.timedelta(
            days=7)
        return self.filter(
            product__FK_Shop__FK_ShopManager=user,
            invoice__status=invoice_models.Invoice.Statuses.COMPLETED,
            invoice__created_datetime__gt=str(
                last_week_start_date.togregorian()),
            invoice__created_datetime__lt=str(
                current_week_start_date.togregorian()),
            product__FK_Shop__Slug=shop_slug,).aggregate(
            amont=Sum('product__Price'))

    def last_month_user_total_sell(self, user, shop_slug):
        now = jdatetime.datetime.now()
        week_start_date = now - jdatetime.timedelta(days=4)
        return self.filter(product__FK_Shop__FK_ShopManager=user,
                           invoice__status=invoice_models.Invoice.Statuses.COMPLETED,
                           product__FK_Shop__Slug=shop_slug,
                           invoice__created_datetime__gt=str(
                               week_start_date.togregorian())).aggregate(
            amont=Sum('product__Price'))
