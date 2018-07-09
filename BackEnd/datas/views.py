from datetime import date
from functools import reduce
from operator import and_

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
# from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from hacks.models import EventParticipation, Event, Pilot
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.views import Response
from rest_framework_expiring_authtoken.models import ExpiringToken
from tools.models import FlipCards

from .models import Tag, Participant, Category, Suggestion, Datasets
from .serializers import DetailsDatasetSerializer, DetailsTagSerializer, MyuserSerializer, CategorySerializer


class CategoriesList(APIView):
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)


class TagList(APIView):
    def get(self, request):
        # Apply tag filters
        if request.GET.get('tags_type') == 'datasets':
            data_tag_ids = [int(tag_id) for tag_id in request.GET.getlist('tag')]
            # print(data_tag_ids)
            if data_tag_ids:
                candidate_datasets = Datasets.objects.filter(tags__pk__in=data_tag_ids)
                valid_dataset_pks = {
                    candidate.pk for candidate in candidate_datasets.prefetch_related('tags').all()
                    if set(data_tag_ids) <= {tag.id for tag in candidate.tags.all()}
                }
                tags = Tag.objects.filter(datasets__pk__in=valid_dataset_pks).distinct()
            else:
                tags = Tag.objects.filter(datasets__isnull=False).distinct()

        elif request.GET.get('tags_type') == 'flipcards':
            flip_tag_ids = [int(tag_id) for tag_id in request.GET.getlist('tag')]
            flipcards = FlipCards.objects.filter(typecard=request.GET.get('category'))
            # print(flip_tag_ids)
            if flip_tag_ids:
                candidate_flipcards = flipcards.objects.filter(language__pk__in=flip_tag_ids)
                valid_flipcards_pks = {
                    candidate.pk for candidate in candidate_flipcards.prefetch_related('language').all()
                    if set(flip_tag_ids) <= {tag.id for tag in candidate.language.all()}
                }
                tags = Tag.objects.filter(flipcards__pk__in=valid_flipcards_pks).distinct()
            else:
                tags = Tag.objects.filter(flipcards__pk__in=flipcards.values('id')).distinct()
        else:
            tags = Tag.objects.all()

        serializer = DetailsTagSerializer(tags, many=True)
        return Response(serializer.data)

    def post(self, request):
        fonc = request.data['fonc']
        response = any

        if fonc == '0':
            response = self.getlanguagetag(request.data)
        if fonc == '1':
            response = self.addnewtag(request.data)
        return Response(response)

    def getlanguagetag(self, data):
        cat = Category.objects.get(name='language')
        tags = Tag.objects.filter(categories=cat)
        serializer = DetailsTagSerializer(tags, many=True)
        return serializer.data

    def addnewtag(self, data):
        cat = Category.objects.get(name='other')
        tag = Tag(categories=cat, name=data['tag'])
        tag.save()
        return 'Tag added'


class DatasetList(APIView):
    @staticmethod
    def get(request):

        tag_ids = [int(tag_id) for tag_id in request.GET.getlist('tag')]
        target = request.GET.get('target', 'all')
        try:
            page = int(request.GET.get('page', 1))
        except ValueError as e:
            error_message = {
                'error': 'Cannot parse page to a valid integer. Value is: {0}'.format(request.GET.get('page'))
            }

            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)
        try:
            page_size = int(request.GET.get('page_size', 10))
        except ValueError as e:
            error_message = {
                'error': 'Cannot parse page size to a valid integer. Value is: {0}'.format(request.GET.get('page_size'))
            }

            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

        datasets = Datasets.objects.filter()

        # Filter by target
        if target == 'all':
            pass  # Do nothing to continue without error
        elif target == 'external':
            datasets = datasets.filter(external=True)
        elif target == 'internal':
            datasets = datasets.filter(external=False)
        else:
            error_message = {
                'error': 'Invalid value for the "target" parameter: {0}'.format(target)
            }

            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)

        txt = request.GET.get('txt')

        if txt != '':
            datasets = datasets.filter(name__icontains=txt)

        # Apply tag filters
        if tag_ids:
            if isinstance(tag_ids, int):
                datasets = datasets.filter(tags__pk=tag_ids)
            else:
                candidate_datasets = datasets.filter(tags__pk__in=tag_ids)
                valid_dataset_pks = {
                    candidate.pk for candidate in candidate_datasets.prefetch_related('tags').all()
                    if set(tag_ids) <= {tag.id for tag in candidate.tags.all()}
                }
                datasets = datasets.filter(pk__in=valid_dataset_pks)  # Get as a QuerySet
                # Alternative implementation that might be hard on the database when there
                # is a lot of tags, but may also be faster:
                # for tag_name in tag_names:
                #     datasets = datasets.filter(tags__name=tag_name)

        if datasets.count() == 0:
            # Avoid creating a paginator for an empty set of data sets
            page = DetailsDatasetSerializer(datasets, many=True).data
            page_count = 0
        else:
            paginator = Paginator(datasets, page_size)
            page = paginator.page(page)
            page_count = paginator.num_pages

        return Response({
            'data_sets': DetailsDatasetSerializer(page, many=True).data,
            'page_count': page_count,
            'hits': datasets.count()
        })

    @staticmethod
    def post(request):
        condition = len(request.data)
        if condition == 1:
            response = DatasetList.updatedataset(request)
        else:
            response = DatasetList.createdataset(request)
        return Response(response)

    @staticmethod
    def createdataset(request):
        external = any
        if request.data['external'] == '1':
            external = 1
            newpath = request.data['externalpath']
        else:
            external = 0
            newpath = request.FILES['path']
        uid = request.data['uid'].replace('"', '')
        user = User.objects.get(id=uid)
        newDataset = Datasets(description=request.data['description'], name=request.data['name'],
                              forma=request.data['formata'], path=newpath, external=external, uploaduser=user)
        newDataset.save()
        # tag retrieval
        tagsid = request.data['tags']
        tagsid = tagsid.replace("[", "")
        tagsid = tagsid.replace("]", "")
        tagarray = tagsid.split(",")

        for record in tagarray:
            instance = Tag.objects.get(pk=record)
            newDataset.tags.add(instance)

        newDataset.save()
        return 'Dataset saved !'

    @staticmethod
    def updatedataset(request):
        dataset = Datasets.objects.get(id=request.data['id'])
        dataset.delete()
        return 'Dataset Deleted!'


class SuggestionManager(APIView):
    def post(self, request):
        func = request.data['func']
        response: any

        if func == '1':
            response = self.deletesuggestion(request)
        elif func == '2':
            response = self.updatesuggestion(request)
        else:
            response = self.newsuggestion(request)

        return Response(response)

    def get(self, request):
        suggestions = Suggestion.objects.all().values('id', 'description', 'provider', 'usage', 'user__first_name',
                                                      'user__last_name', 'accepted')
        return Response(suggestions)

    def newsuggestion(self, request):
        user_inst = User.objects.get(id=request.data['user'])
        newSuggestion = Suggestion(description=request.data['description'], provider=request.data['provider'],
                                   usage=request.data['usage'], user=user_inst)
        newSuggestion.save()
        return 'Suggestion noted !'

    def deletesuggestion(self, request):
        suggestion = Suggestion.objects.get(id=request.data['id'])
        suggestion.delete()
        return 'Suggestion deleted!'

    def updatesuggestion(self, request):
        suggestion = Suggestion.objects.get(id=request.data['id'])
        suggestion.accepted = request.data['accepted'].lower() == 'true'
        suggestion.save()
        return 'Suggestion updated!'


class DatasetListSelected(APIView):
    def get(self, request, data_id):
        spesific = Datasets.objects.filter(id=data_id)
        serializer = DetailsDatasetSerializer(spesific, many=True)
        return Response(serializer.data)


class ManagingUser(APIView):
    def post(self, request):
        responses = 'Error';
        parameters = request.data
        condition = len(parameters)
        if (condition == 1):
            responses = self.sendnewmail(request)
        elif (condition == 2):
            responses = self.updatepassword(request)
        return Response(responses)

    def updatepassword(self, request):
        msg = 'password updated';
        user = User.objects.get(id=request.data['uid'])
        user.set_password(request.data['pswd'])
        user.save()
        # update token
        if (self.tokendelet(request.data['uid'])):
            msg = 'error with token'
        return msg

    def tokendelet(self, request):
        userD = User.objects.get(id=request)
        token = ExpiringToken.objects.get(user=userD)
        token.delete()
        return '1'

    def sendnewmail(self, request):
        mail = request.data['mail']
        _user = User.objects.get(username=mail)
        token = ExpiringToken.objects.get_or_create(user=_user)
        msg = 'Error encountered';
        # Should install Crypto to encrypte and decrypt the token before and after sending the mail
        link = settings.API_LINK + '/reseet?variable=' + str(_user.id) + '0mbt0' + str(token[0]);
        html_content = '<p>You have asked for a new password.</p></br>Please follow the<a href="' + link + '">link</a>.';
        subject, from_email, to = 'Forgot your password!', settings.EMAIL_HOST_USER, mail
        emailcontent = EmailMultiAlternatives(subject, '', from_email, [to])
        emailcontent.attach_alternative(html_content, "text/html")
        if (emailcontent.send()):
            msg = 'mail sent with sucess';
        return msg


class NewUser(APIView):
    def get(self, request, event_id):
        allusers = []
        instance = Event.objects.get(id=event_id)
        participants = EventParticipation.objects.filter(event=instance)
        for item in participants:
            allusers.append(str(item.participant))
        return Response(allusers)

    def post(self, request):
        response = any
        if not User.objects.filter(email=request.data['email']).exists():
            user = User.objects.create_user(
                request.data['email'], request.data['email'], request.data['password']
            )
            user.last_name = request.data['last_name']
            user.first_name = request.data['firstName']
            user.participant.profession = request.data['profession']
            user.save()
            if request.data['pilot']:
                user.is_staff = True
                user.save()
                pilot = Pilot.objects.get(id=request.data['pilot'])
                pilot.user.add(user)
            # user.participant.date_birth = datetime.strptime(request.data['birthDate'], '%d-%m-%Y') #For some reason wont accept this values in no format
            if request.data['func'] == '0':
                response = self.sendWelcome(request.data)
            elif request.data['func'] == '1':
                response = self.sendConfirm(request.data)
            return Response(response)
        else:
            return Response('user exists', status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return Response(response)

    def sendConfirm(self, request):
        _user = User.objects.get(email=request['email'])
        if request['pilot']:
            if not Pilot.objects.filter(country=request['pilot']).exists():
                pilot = Pilot(country=request['pilot'])
                pilot.save()
                pilot.user.add(_user)
                pilot.save()
            else:
                pilot = Pilot.objects.get(country=request['pilot'])
                pilot.user.add(_user)
                pilot.save()
        if (send_mail(
                'Welcome to Open Data Lab !',
                'Hi ' + request['firstName'] + ' ' + request['last_name'] + ', please use : ' + request[
                    'email'] + ' as your username to access the platform.',
                settings.EMAIL_HOST_USER,
                [request['email']],
                fail_silently=False
        )):
            return '200'
        return '350'

    def sendWelcome(self, data):
        email = data['email']
        _user = User.objects.get(email=email)
        facilitator = User.objects.get(id=data['facilitatorID'])
        token = ExpiringToken.objects.get_or_create(user=_user)
        link = settings.API_LINK + '/reseet?variable=' + str(_user.id) + '0mbt0' + str(token[0]);
        if (send_mail(
                'Welcome to Open Data Lab !',
                '<p>Hello ' + data[
                    'email'] + ', ' + facilitator.first_name + ' ' + facilitator.last_name + ' has invited you to the Open data lab platform</p><p>Please follow this <a href="' + link + '">link</a> to set your password: </p>',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
        )):
            return '200'
        return '350'


class MyUser(APIView):
    # Responsible for verifying token and user are identical
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        part = Participant.objects.all()
        serializer = MyuserSerializer(part, many=True)
        return Response(serializer.data)

    def post(self, request):
        fonc = request.data['fonc']
        response = any

        # user = authenticate(username=dataR['username'], password=dataR['password'])
        if fonc == '2':
            response = self.logout(request)
        elif fonc == '4':
            response = self.fetchloginfo(request)
        elif fonc == '1':
            response = self.userinfo(request)
        elif fonc == '0':
            response = self.authentif(request)
        elif (fonc == '5'):
            response = self.updateuser(request)
        elif (fonc == '6'):
            response = self.userexist(request.data)
        return Response(response)

    def fetchloginfo(self, request):
        token = request.META['HTTP_AUTHORIZATION']
        token = token.replace('Token ', '')
        getall = Token.objects.filter(key=token).values_list('user_id', flat=True)
        data = {'id': str(getall[0]), 'status': 200}
        return data

    def userinfo(self, request):
        part = Participant.objects.select_related('user').get(user_id=request.data['id'])
        today = date.today()
        age = today.year - part.date_birth.year - (
                (today.month, today.day) < (part.date_birth.month, part.date_birth.day))
        member = str(part.user.date_joined.month) + '/' + str(part.user.date_joined.day) + '/' + str(
            part.user.date_joined.year)
        data = {'id': request.data['id'], 'first_name': part.user.first_name, 'last_name': part.user.last_name,
                'email': part.user.email, 'joindate': member, 'profession': part.profession, 'age': age,
                'super': part.user.is_staff}  # , 'img': part.imgpath}
        return data

    def userexist(self, data):
        user = User.objects.filter(email=data['email'])
        if (user.count() > 0):
            return {'exists': True}
        else:
            return {'exists': False}

    """
        This is to verify is user is connected and the token is correct,
        sused only for the front end to identify redirecting viewss
        #Should be changed to create tokens on the fly and delete them when users logout, ovveride the ObtainAuthToken and use this view for authentification
    """

    def authentif(self, request):
        msg = '415';
        if request.user.is_authenticated():
            msg = '200';
        return msg;

    def logout(self, request):
        request.user.auth_token.delete();
        # data = {'status': 200, 'msg': 'session closed'};
        # return Response(data);
        return '200';
        # return Response(status=status.HTTP_202_ACCEPTED);

    def updateuser(self, request):
        user = User.objects.get(id=request.data['id'])
        user.first_name = request.data['newfirst']
        user.last_name = request.data['newlast']
        user.participant.profession = request.data['newprof']
        user.email = request.data['newemail']

        user.save()

        return 'successfully updated user info'
