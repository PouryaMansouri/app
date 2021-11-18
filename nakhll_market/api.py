import random
import pandas as pd
from django.shortcuts import get_object_or_404
from django.http import response
from django.http.response import Http404
from django.db.models import Q, F, Count
from django.db.models.aggregates import Sum
from django.db.models.expressions import Case, When
from django.contrib.auth.models import User
from django.utils.text import slugify
from rest_framework import generics, routers, status, views, viewsets
from rest_framework import permissions, filters, mixins
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, AuthenticationFailed
from rest_framework.decorators import action
from django_filters import rest_framework as restframework_filters
from nakhll_market.models import (
    Alert, AmazingProduct, Comment, NewCategory, Product, ProductBanner, Shop, Slider, Category, Market, State, BigCity, City, SubMarket,
    LandingPageSchema, ShopPageSchema,
    )
from nakhll_market.serializers import (
    AmazingProductSerializer, Base64ImageSerializer, NewCategoryProductCountSerializer, NewProfileSerializer, ProductCommentSerializer, ProductDetailSerializer, ProductImagesSerializer,
    ProductSerializer, ProductUpdateSerializer, ShopProductSerializer, ShopSerializer, ShopSimpleSerializer,SliderSerializer, ProductPriceWriteSerializer,
    CategorySerializer, FullMarketSerializer, CreateShopSerializer, ProductInventoryWriteSerializer,
    ProductListSerializer, ProductWriteSerializer, ShopAllSettingsSerializer, ProductBannerSerializer,
    ProductSubMarketSerializer, StateFullSeraializer, SubMarketProductSerializer, SubMarketSerializer,
    LandingPageSchemaSerializer, ShopPageSchemaSerializer, UserOrderSerializer,
    NewCategorySerializer, NewCategoryChildSerializer, NewCategoryParentChildSerializer, NewCategoryParentSerializer
    )
from restapi.permissions import IsFactorOwner, IsProductOwner, IsShopOwner, IsProductBannerOwner
from restapi.serializers import ProfileSerializer
from accounting_new.models import Invoice
from nakhll_market.filters import ProductFilter
from nakhll_market.permissions import IsInvoiceOwner
from nakhll_market.paginators import StandardPagination
from nakhll_market.product_bulk_operations import BulkException, BulkProductHandler

class SliderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SliderSerializer
    permission_classes = [permissions.AllowAny, ]
    search_fields = ('Location', )
    filter_backends = (filters.SearchFilter,)
    queryset = Slider.objects.filter(Publish=True)
    

class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Category.objects.get_category_publush_avaliable()

class AmazingProductViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AmazingProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return AmazingProduct.objects.get_amazing_products()

class LastCreatedProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Product.objects.get_last_created_products()

class LastCreatedDiscountedProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Product.objects.get_last_created_discounted_products()

class RandomShopsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ShopSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Shop.objects.get_random_shops()

class RandomProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Product.objects.get_random_products()

class MostDiscountPrecentageProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Product.objects.get_most_discount_precentage_products()

class MostSoldShopsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ShopSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        return Shop.objects.most_last_week_sale_shops()

class ShopProductsViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.ListModelMixin):
    serializer_class = ShopProductSerializer
    permission_classes = [permissions.AllowAny, ]
    product_slug = None
    lookup_field = 'FK_Shop__Slug'

    def get_queryset(self):
        filter_query = {self.lookup_field: self.product_slug, 'Publish': True, 'Available': True}
        return Product.objects.filter(**filter_query)

    def retrieve(self, request, *args, **kwargs):
        self.product_slug = self.kwargs.get(self.lookup_field)
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        if not self.product_slug:
            raise Http404
        return super().list(request, *args, **kwargs)
     



class UserProductViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                         mixins.ListModelMixin, mixins.UpdateModelMixin):
    permission_classes = [permissions.IsAuthenticated, IsProductOwner]
    queryset = Product.objects.all().order_by('-DateCreate')
    lookup_field = 'ID'

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return ProductUpdateSerializer
        elif self.action in ['list', 'retrieve']:
            return ProductListSerializer
        else:
            return ProductWriteSerializer


    def generate_unique_slug(self, title):
        ''' Generate new unique slug for Product Model 
            NOTE: This fucntion should move to utils
        '''
        slug = slugify(title, allow_unicode=True)
        counter = 1
        new_slug = slug
        while(Product.objects.filter(Slug=new_slug).exists()):
            new_slug = f'{slug}_{counter}'
            counter += 1
        return new_slug

    def perform_create(self, serializer):
        data = serializer.validated_data
        # post_range = data.pop('post_range_cities')
        shop = data.get('FK_Shop')
        title = data.get('Title')

        # Check if target shop is owned by user or not
        if shop.FK_ShopManager != self.request.user:
            raise ValidationError({'details': 'Shop is not own by user'})

        slug = self.generate_unique_slug(title)
        product_extra_fileds = {'Publish': True, 'Slug': slug}
        # TODO: This behavior should be inhanced later
        #! Check if price have dicount or not
        #! Swap Price and OldPrice value if discount exists
        #! Note that, request should use OldPrice as price with discount
        # Convert price and old price from Toman to Rial to store in DB
        old_price = data.get('OldPrice', 0) * 10
        price = data.get('Price', 0) * 10
        if old_price:
            product = serializer.save(OldPrice=price, Price=old_price, **product_extra_fileds)
        else:
            product = serializer.save(OldPrice=old_price, Price=price, **product_extra_fileds)
        # product.post_range_cities.add(*post_range) 
        
        # TODO: Check if product created successfully and published and alerts created as well
        Alert.objects.create(Part='6', FK_User=self.request.user, Slug=product.ID)

    def perform_update(self, serializer):
        data = serializer.validated_data
        # post_range = data.pop('post_range_cities')
        ID = self.kwargs.get('ID')

        # TODO: This behavior should be inhanced later
        #! Check if price have dicount or not
        #! Swap Price and OldPrice value if discount exists
        #! Note that, request should use OldPrice as price with discount
        # Convert price and old price from Toman to Rial to store in DB
        old_price = data.get('OldPrice', 0) * 10
        price = data.get('Price', 0) * 10
        if old_price:
            product = serializer.save(OldPrice=price, Price=old_price)
        else:
            product = serializer.save(OldPrice=old_price, Price=price)
        # product.post_range_cities.add(*post_range) 

        # TODO: Check if product created successfully and published and alerts created as well
        Alert.objects.create(Part='7', FK_User=self.request.user, Slug=ID)


class ProductsViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    pagination_class = StandardPagination
    filter_class = ProductFilter
    filter_backends = (restframework_filters.DjangoFilterBackend, filters.OrderingFilter)
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny, ]
    ordering_fields = ('Title', 'Price', 'DiscountPrecentage', 'DateCreate', )

    def get_queryset(self):
        query = self.request.GET.get('search', '')
        queryset = Product.objects.select_related('FK_SubMarket', 'FK_Shop').filter(Publish=True)
        queryset = queryset.annotate(DiscountPrecentage=Case(
            When(OldPrice__gt=0, then=(
                (F('OldPrice') - F('Price')) * 100 / F('OldPrice'))
            ), default=0))
        queryset = queryset.annotate(submarket_products=Count('FK_SubMarket__Product_SubMarket', Q(FK_SubMarket__Product_SubMarket__Title__contains=query)))
        queryset = queryset.order_by('-submarket_products')
        return queryset


    def get_most_product_submarkets(self, query):
        queryset = SubMarket.objects.filter(Available=True, Publish=True)
        queryset = queryset.filter(Product_SubMarket__Title__contains=query)
        queryset = queryset.annotate(product_count=Count('Product_SubMarket'))
        return queryset.order_by('-product_count').values_list('ID')




class ProductDetailsViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.AllowAny, ]
    lookup_field = 'Slug'
    queryset = Product.objects.select_related('FK_SubMarket', 'FK_Shop')

class ProductCommentsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductCommentSerializer
    permission_classes = [permissions.AllowAny, ]
    lookup_field = 'FK_Product__Slug'
    product_slug = None
    def get_queryset(self):
        filter_query = {self.lookup_field: self.product_slug, 'FK_Pater': None}
        return Comment.objects.filter(**filter_query).select_related('FK_Product')

    def retrieve(self, request, *args, **kwargs):
        self.product_slug = self.kwargs.get(self.lookup_field)
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        if not self.product_slug:
            raise Http404
        return super().list(request, *args, **kwargs)
        

class ProductRelatedItemsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    pagination_class = StandardPagination
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]
    lookup_field = 'Slug'
    product = None

    def get_queryset(self):
        return Product.objects.filter(
                    Available = True, Publish = True, Status__in = ['1', '2', '3'],
                    FK_Category__in = self.product.FK_Category.all())

    def retrieve(self, request, *args, **kwargs):
        self.product = Product.objects.get(Slug=self.kwargs.get(self.lookup_field))
        return self.list(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        if not self.product:
            raise Http404
        return super().list(request, *args, **kwargs)


class ProductsInSameFactorViewSet(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny, ]

    def get_queryset(self):
        id = self.kwargs.get('ID')
        return Product.objects.get_products_in_same_factor(id)
 
 
class MarketList(generics.ListAPIView):
    serializer_class = FullMarketSerializer
    permission_classes = [permissions.AllowAny, ]
    # queryset = Market.objects.filter(Available=True, Publish=True)
        
    def list(self, request, *args, **kwargs):
        query = self.request.GET.get('query')
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        # serializer = self.get_serializer(queryset, many=True, context={'query': query})
        return Response(serializer.data)

    def get_queryset(self):
        query = self.request.GET.get('query')
        if query:
            queryset = Market.objects.filter(FatherMarket__Product_SubMarket__Title__contains=query, Available=True, Publish=True)
            # queryset = SubMarket.objects.filter(Product_SubMarket__Title__contains=query, Available=True, Publish=True)
            queryset = queryset.annotate(product_count=Count('FatherMarket__Product_SubMarket'))
            return queryset.order_by('product_count')
        return Market.objects.filter(Available=True, Publish=True)

class SubMarketList(generics.ListAPIView):
    permission_classes = [permissions.AllowAny, ]
    serializer_class = SubMarketProductSerializer

    def get_queryset(self):
        query = self.request.GET.get('q')
        queryset = SubMarket.objects.filter(Available=True, Publish=True)
        if not query:
            return queryset.none()
        queryset = queryset.filter(Product_SubMarket__Title__contains=query)
        queryset = queryset.annotate(product_count=Count('Product_SubMarket'))
        return queryset.order_by('-product_count')




class GetShopWithSlug(views.APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, ]

    def get(self, request, format=None):
        shop_slug = request.GET.get('slug')
        shop = get_object_or_404(Shop, Slug=shop_slug)
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

class GetShop(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, ]
    serializer_class = ShopSerializer
    queryset = Shop.objects.filter(Available=True, Publish=True)
    lookup_field = 'Slug'

class GetShopList(viewsets.GenericViewSet, mixins.ListModelMixin):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, ]
    serializer_class = ShopSimpleSerializer
    queryset = Shop.objects.filter(Available=True, Publish=True).select_related('FK_ShopManager', 'FK_ShopManager__User_Profile', )




class CreateShop(generics.CreateAPIView):
    serializer_class = CreateShopSerializer
    permission_classes = [permissions.IsAuthenticated, ]
    def get_queryset(self):
        return Shop.objects.filter(FK_ShopManager=self.request.user)

    def generate_unique_slug(self, title):
        ''' Generate new unique slug for Shop Model 
            NOTE: This fucntion should move to utils
        '''
        slug = slugify(title, allow_unicode=True)
        counter = 1
        new_slug = slug
        while(Shop.objects.filter(Slug=new_slug).exists()):
            new_slug = f'{slug}_{counter}'
            counter += 1
        return new_slug

    def perform_create(self, serializer):
        # super().perform_create(serializer)
        # TODO: REFACTOR: Replace state, bigcity and city id to string in front side,
        # TODO: REFACTOR: and this gets do not need anymore
        state_id = serializer.validated_data.get('State')
        bigcity_id = serializer.validated_data.get('BigCity')
        city_id = serializer.validated_data.get('City')
        title = serializer.validated_data.get('Title')
        slug = serializer.validated_data.get('Slug')
        if not slug:
            slug = self.generate_unique_slug(title)
        elif Shop.objects.filter(Slug=slug).exists():
            raise ValidationError({'details': 'شناسه حجره از قبل موجود است'})

        state = get_object_or_404(State, id=state_id)
        bigcity = get_object_or_404(BigCity, id=bigcity_id)
        city = get_object_or_404(City, id=city_id)

        new_shop = serializer.save(FK_ShopManager=self.request.user, Publish=True, 
                                State=state.name, BigCity=bigcity.name, City=city.name, Slug=slug)
        Alert.objects.create(Part='2', FK_User=self.request.user, Slug=new_shop.ID)







class CheckShopSlug(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ]
    def get(self, request, format=None):
        shop_slug = request.GET.get('slug')
        try:
            shop = Shop.objects.get(Slug=shop_slug)
            return Response({'shop_slug': shop.ID})
        except Shop.DoesNotExist:
            return Response({'shop_slug': None})
class CheckProductSlug(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ]
    def get(self, request, format=None):
        product_slug = request.GET.get('slug')
        try:
            product = Product.objects.get(Slug=product_slug)
            return Response({'product_slug': product.ID})
        except Product.DoesNotExist:
            return Response({'product_slug': None})
class AddSubMarketToProduct(views.APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, format=None):
        try:
            serializer = ProductSubMarketSerializer(data=request.data)
            if serializer.is_valid():
                product_id = serializer.data.get('product')
                submarket_ids = serializer.data.get('submarkets', [])
                product = Product.objects.get(ID=product_id)
                self.check_object_permissions(request, product)
                for submarket_id in submarket_ids:
                    submarket = SubMarket.objects.get(ID=submarket_id)
                    submarket.Product_SubMarket.add(product)

                # TODO: Check if created product alert display images and submarkets
                # TODO: or I should create an alert for submarkets and images

                return Response({'details': 'done'}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response({'details': 'Bad Request'}, status=status.HTTP_400_BAD_REQUEST)

class AddImagesToProduct(views.APIView):
    # parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, format=None):
        try:
            serializer = ProductImagesSerializer(data=request.data)
            # if serializer.is_valid() and 'images' in request.FILES:
            if serializer.is_valid():
                product_id = serializer.validated_data.get('product')
                images = serializer.validated_data.get('images')
                product = Product.objects.get(ID=product_id)
                self.check_object_permissions(request, product)
                
                # Save first image in product.NewImage
                product_main_image = images[0]
                product.Image = product_main_image
                product.save()

                # Save all images in product.Product_Banner
                # Set Alert for each image
                for image in images:
                    product_banner = ProductBanner.objects.create(FK_Product=product, Image=image, Publish=True)
                    Alert.objects.create(Part='8', FK_User=request.user, Slug=product_banner.id)


                return Response({'details': 'done'}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response({'details': 'Bad Request'}, status=status.HTTP_400_BAD_REQUEST)

class ProductBannerViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin, 
                        mixins.DestroyModelMixin):
    permission_classes = [permissions.IsAuthenticated, IsProductBannerOwner]
    lookup_field = 'id'
    queryset = ProductBanner.objects.all()
    serializer_class = ProductBannerSerializer

    def perform_create(self, serializer):
        product_banner = serializer.save(Publish=True)
        Alert.objects.create(Part='8', FK_User=self.request.user,
                             Slug=product_banner.id)


class ShopMultipleUpdatePrice(views.APIView):
    #TODO: Swap OldPrice and Price
    permission_classes = [permissions.IsAuthenticated,]
    def patch(self, request, format=None):
        serializer = ProductPriceWriteSerializer(data=request.data, many=True)
        user = request.user
        if serializer.is_valid():
            price_list = serializer.data
            ready_for_update_products = []
            for price_item in price_list:
                try:
                    product = Product.objects.get(Slug=price_item.get('Slug'))
                    old_price = price_item.get('OldPrice')
                    price = price_item.get('Price')
                    if product.FK_Shop.FK_ShopManager == user:
                        # TODO: This behavior should be inhanced later
                        #! Check if price have dicount or not
                        #! Swap Price and OldPrice value if discount exists
                        #! Note that, request should use OldPrice as price with discount
                        if old_price:
                            product.OldPrice = price
                            product.Price = old_price
                        else:
                            product.OldPrice = old_price
                            product.Price = price
                        ready_for_update_products.append(product)

                except:
                    pass
            Product.objects.bulk_update(ready_for_update_products, ['Price', 'OldPrice'])
            return Response({'details': 'done'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ShopMultipleUpdateInventory(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ]
    def patch(self, request, format=None):
        serializer = ProductInventoryWriteSerializer(data=request.data, many=True)
        user = request.user
        # user = User.objects.get(id=72)
        if serializer.is_valid():
            price_list = serializer.data
            ready_for_update_products = []
            for inventory_item in price_list:
                try:
                    product = Product.objects.get(Slug=inventory_item.get('Slug'))
                    inventory = inventory_item.get('Inventory')
                    if product.FK_Shop.FK_ShopManager == user:
                        product.Inventory = inventory
                        ready_for_update_products.append(product)
                except:
                    pass
            Product.objects.bulk_update(ready_for_update_products, ['Inventory'])
            return Response({'details': 'done'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AllShopSettings(views.APIView):
    # TODO: Check this class entirely
    permission_classes = [permissions.IsAuthenticated, IsShopOwner]
    def get_object(self, shop_slug, user):
        return get_object_or_404(Shop, Slug=shop_slug)
    def get(self, request, shop_slug, format=None):
        user = request.user
        shop = self.get_object(shop_slug, user)
        self.check_object_permissions(request, shop)
        serializer = ShopAllSettingsSerializer(shop)
        return Response(serializer.data)

    def patch(self, request, shop_slug, format=None):
        user = request.user
        shop = self.get_object(shop_slug, user)
        self.check_object_permissions(request, shop)
        serializer = ShopAllSettingsSerializer(data=request.data, instance=shop)
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data)

class BankAccountShopSettings(views.APIView):
    # TODO: Check this class entirely
    permission_classes = [permissions.IsAuthenticated, ]
    def get_object(self, shop_slug, user):
        return get_object_or_404(Shop, Slug=shop_slug)
    def put(self, request, shop_slug, format=None):
        user = request.user
        shop = self.get_object(shop_slug, user)
        self.check_object_permissions(request, shop)
        serializer = ShopBankAccountSettingsSerializer(data=request.data, instance=shop)
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data)

class SocialMediaShopSettings(views.APIView):
    # TODO: Check this class entirely
    permission_classes = [permissions.IsAuthenticated, ]
    def get_object(self, shop_slug, user):
        return get_object_or_404(Shop, Slug=shop_slug)
    def put(self, request, shop_slug, format=None):
        user = request.user
        shop = self.get_object(shop_slug, user)
        self.check_object_permissions(request, shop)
        serializer = SocialMediaAccountSettingsSerializer(data=request.data, instance=shop)
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data)


class ImageShopSettings(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ]
    def get_object(self, shop_slug):
        return get_object_or_404(Shop, Slug=shop_slug)
    def put(self, request, shop_slug, format=None):
        shop = self.get_object(shop_slug)
        self.check_object_permissions(request, shop)
        serializer = Base64ImageSerializer(data=request.data)
        if serializer.is_valid():
            image = serializer.validated_data.get('image')
            shop.Image = image
            shop.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.data)


class StateFullViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    permission_classes = [permissions.AllowAny, ]
    queryset = State.objects.all()
    serializer_class = StateFullSeraializer


class UserProfileViewSet(viewsets.GenericViewSet):
    '''Viewset for user profile '''
    permission_classes = [permissions.IsAuthenticated, ]
    queryset = User.objects.all()
    serializer_class = ProfileSerializer

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        user = request.user
        serializer = NewProfileSerializer(user.User_Profile)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'])
    def edit_me(self, request):
        user = request.user
        serializer = NewProfileSerializer(user.User_Profile, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserOrderHistory(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    permission_classes = [permissions.IsAuthenticated, IsInvoiceOwner]
    queryset = Invoice.objects.all()
    serializer_class = UserOrderSerializer

    def get_queryset(self):
        return Invoice.objects.filter(cart__user=self.request.user)


class LandingPageSchemaViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    permission_classes = [permissions.AllowAny, ]
    serializer_class = LandingPageSchemaSerializer

    def get_queryset(self):
        return LandingPageSchema.objects.get_published_schema(self.request)

class ShopPageSchemaViewSet(views.APIView):
    permission_classes = [permissions.AllowAny, ]
    serializer_class = ShopPageSchemaSerializer

    def get_object(self, shop_id):
        return get_object_or_404(Shop, Slug=shop_id)

    def get(self, request, shop_id, format=None):
        shops = ShopPageSchema.objects.get_published_schema(self.request, shop_id)
        serializer = ShopPageSchemaSerializer(shops, many=True)
        return Response(serializer.data)

class GroupProductCreateExcel(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopOwner]
    bulk_type = BulkProductHandler.BULK_TYPE_CREATE

    def get_object(self, shop_slug):
        shop = get_object_or_404(Shop, Slug=shop_slug)
        self.check_object_permissions(self.request, shop)
        return shop

    def post(self, request, shop_slug, format=None):
        shop = self.get_object(shop_slug)
        csv_file = request.FILES.get('product-excel-upload')
        zip_file = request.FILES.get('product-zip-file')
        bulk_product_handler = BulkProductHandler(shop=shop, images_zip_file=zip_file, bulk_type=self.bulk_type)
        try:
            result = bulk_product_handler.parse_csv(csv_file)
        except BulkException as ex:
            return Response(str(ex), status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

class GroupProductUpdateExcel(GroupProductCreateExcel ,views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopOwner]
    bulk_type = BulkProductHandler.BULK_TYPE_UPDATE

class GroupProductUndo(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopOwner]

    def get_object(self, shop_slug):
        shop = get_object_or_404(Shop, Slug=shop_slug)
        self.check_object_permissions(self.request, shop)
        return shop

    def get(self, request, shop_slug, format=None):
        shop = self.get_object(shop_slug)
        bulk_product_handler = BulkProductHandler(shop=shop)
        try:
            bulk_product_handler.undo_last_changes()
        except BulkException as ex:
            return Response(str(ex), status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Undo sent'})

class GroupProductUndo(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsShopOwner]

    def get_object(self, shop_slug):
        shop = get_object_or_404(Shop, Slug=shop_slug)
        self.check_object_permissions(self.request, shop)
        return shop

    def get(self, request, shop_slug, format=None):
        shop = self.get_object(shop_slug)
        bulk_product_handler = BulkProductHandler(shop=shop, is_undo_operation=True)
        try:
            result = bulk_product_handler.undo_last_changes()
        except BulkException as ex:
            return Response(str(ex), status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class MostSoldProduct(views.APIView):
    permission_classes = [permissions.AllowAny, ]
    serializer_class = ProductSerializer

    def get_object(self):
        return Product.objects.get_most_sold_product()

    def get(self, request, format=None):
        product = self.get_object()
        serializer = ProductSerializer(product, many=True)
        return Response(serializer.data)


class CategoryViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    permission_classes = [permissions.AllowAny, ]
    queryset = NewCategory.objects.all_ordered()
    serializer_class = NewCategoryParentSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        if self.action == 'list':
            self.serializer_class = NewCategoryChildSerializer
            return NewCategory.objects.get_root_categories()
        return NewCategory.objects.all_ordered()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            max_depth = int(self.request.query_params.get('max_depth', -1))
        except ValueError:
            max_depth = -1
        context['max_depth'] = max_depth
        return context
    

    @action(methods=['GET'], detail=False)
    def category_product_count(self, request):
        query = request.GET.get('q', None)
        queryset = NewCategory.objects.categories_with_product_count(query)
        return Response(NewCategoryProductCountSerializer(queryset, many=True).data)