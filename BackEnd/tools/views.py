from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from django.shortcuts import render
from .models import Outil, Hackproces, FlipCards, Projects, ProjectFiles
from hacks.models import WorkGroups, Event, Pilot
from .serializers import OutilSerializer, HackprocesSerializer, FlipCardSerializer, ProjectSerializer
from rest_framework.views import status, APIView, Response
from corsheaders.signals import check_request_enabled
from django.contrib.auth.models import User
from datas.models import Tag
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


class OutilList(APIView):
    def get(self, request):
        outilss = Outil.objects.all()
        serializer = OutilSerializer(outilss, many=True)
        return Response(serializer.data)


class OutilSelected(APIView):
    def get(self, request, outil_id):
        spesific = Outil.objects.filter(id=outil_id)
        serializer = OutilSerializer(spesific, many=True)
        return Response(serializer.data)


class HackProcesList(APIView):
    def get(self, request):
        hackprocess = Hackproces.objects.all()
        serializer = HackprocesSerializer(hackprocess, many=True)
        return Response(serializer.data)

    def post(self, request):
        # request.data['lng'] = request.data['lng'].replace('"', '')
        # lng = Tag.objects.get(id=request.data['lng'])
        # print('Event '+str(request.data['tools']))
        event = Event.objects.get(id=request.data['event'])

        Eventprocess = Hackproces(for_event=event)
        Eventprocess.save()

        my_list = []
        for item in request.data['tools']:
            tool = Outil.objects.get(id=item)
            # my_list.extend(tool)
            Eventprocess.outil_used.add(tool)

        Eventprocess.save()
        return Response('success')


class HackProcesSelected(APIView):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, proces_id):
        spesific = Hackproces.objects.filter(for_event=proces_id)
        serializer = HackprocesSerializer(spesific, many=True)
        my_list = []
        if (len(serializer.data) > 0):
            record = (serializer.data[0]['outil_used'])
            for tool_id in record:
                tool = Outil.objects.filter(id=tool_id).values('id', 'name', 'categorys')
                my_list.extend(tool)
        return Response(my_list)

    def delete(self, request, proces_id):
        process = Hackproces.objects.get(for_event=proces_id)
        process.outil_used.remove();
        process.delete()
        return Response('Success');


# searsh query
class SelectedToolsForEvent(APIView):
    def get(self, request, event_id):
        spesific = Hackproces.objects.filter(for_event=event_id)
        serializer = HackprocesSerializer(spesific, many=True)
        return Response(serializer.data)


class FlipcardManger(APIView):
    # Provoque une erreur ?!!
    # authentication_classes = (TokenAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def get(self, request):
        category = request.GET.get('category')

        page_size = request.GET.get('page_size')
        page = request.GET.get('page')

        tag_ids = [int(tag_id) for tag_id in request.GET.getlist('tag')]

        record = FlipCards.objects.filter(typecard=category, user_id=request.user.id)


        # Apply tag filters
        if tag_ids:
            candidate_record = record.filter(language__pk__in=tag_ids)
            valid_record_pks = {
               candidate.pk for candidate in candidate_record.prefetch_related('tags').all()
                if set(tag_ids) <= {tag.id for tag in candidate.tags.all()}
            }
            record = record.filter(pk__in=valid_record_pks)  # Get as a QuerySet
            # Alternative implementation that might be hard on the database when there
            # is a lot of tags, but may also be faster:
            # for tag_name in tag_names:
            #     datasets = datasets.filter(tags__name=tag_name)

        if record.count() == 0:
            # Avoid creating a paginator for an empty set of data sets
            page = FlipCardSerializer(record, many=True).data
            page_count = 0
        else:
            paginator = Paginator(record, page_size)
            page = paginator.page(page)
            page_count = paginator.num_pages

        return Response({
            'flipcards': FlipCardSerializer(page, many=True).data,
            'page_count': page_count
        })

        # if record.count() <= 0:
        #     return Response(FlipCardSerializer(record, many=True).data)
        #
        # paginator = Paginator(record, page_size)
        # page = paginator.page(page)
        #
        # ser = FlipCardSerializer(page, many=True)
        # return Response(ser.data)

    def post(self, request):
        fonction = request.data['fonc']
        response = any
        if fonction == '0':
            response = self.addcard(request)
        elif fonction == '1':
            response = self.editcard(request)
        elif fonction == '2':
            response = self.deletecard(request.data)
        elif fonction == '3':
            response = self.fetchcard(request.data)
        return Response(response)

    def addcard(self, request):
        request.data['userID'] = request.data['userID'].replace('"', '')
        # .data['lng'] =
        user = User.objects.get(id=request.data['userID'])
        fileLNK: any
        try:
            fileLNK = request.FILES['path']
        except:
            fileLNK = ''
        newCard = FlipCards(typecard=request.data['type'], title=request.data['title'],
                            description=request.data['desc'], link=request.data['link'], path=fileLNK, user=user)
        newCard.save()
        tagsid = request.data['tags']
        # print(tagsid)
        tagsid = tagsid.replace('"', '')
        tagsid = tagsid.replace("[", "")
        tagsid = tagsid.replace("]", "")
        tagarray = tagsid.split(",")
        # print(tagarray)
        for id in tagarray:
            #print(id)
            newCard.language.add(Tag.objects.get(id=id))
        newCard.save()
        return 'Success'

    def editcard(self, request):
        record = FlipCards.objects.get(id=request.data['id'])
        record.title = request.data['title']
        record.link = request.data['link']
        record.description = request.data['desc']
        if (len(request.data) > 5):
            record.path = request.FILES['path']
        record.save()
        return 'Success'

    def deletecard(self, data):
        record = FlipCards.objects.get(id=data['id'])
        record.delete()
        return 'Success'

    def fetchcard(self, data):
        record = FlipCards.objects.filter(typecard=data['cardtype'])

        if record.count() <= 0:
            return FlipCardSerializer(record, many=True).data

        paginator = Paginator(record, int(data['amount']))
        page = paginator.page(int(data['page']))

        ser = FlipCardSerializer(page, many=True)
        return ser.data


class MyProjects(APIView):
    def get(self, request):
        query = WorkGroups.objects.filter(users=request.user.id).values('event_id')
        projectslist = []
        for item in query:
            try:
                project = Projects.objects.filter(id=item['event_id']).values('id', 'title', 'created', 'version')
                projectslist.extend(project)
            except Exception:
                pass
        # projects = ProjectSerializer(projectslist, many=True)
        return Response(projectslist)

    def post(self, request):
        fonction = request.data['fonc']
        response = any
        if fonction == '0':
            response = self.getCountryList(request)
        # elif fonction == '1':
        #    response = self.editcard(request)
        return Response(response)

    def getCountryList(self, request):
        pilots = Pilot.objects.values('id', 'country', 'imgname').distinct();
        return pilots


class ProjectManagers(APIView):
    # authentication_classes = (TokenAuthentication,)
    # permission_classes = (IsAuthenticated,)

    def get(self, request, event_ID):
        event = Event.objects.get(id=event_ID)
        thegroup = WorkGroups.objects.get(users=request.user.id, event=event)
        project = Projects.objects.get(group=thegroup)
        projectserialized = ProjectSerializer(project)
        return Response(projectserialized.data)

    def post(self, request):
        fonction = request.data['fonc']
        response = any
        if fonction == '0':
            response = self.defaultaddproject(request)
        if fonction == '1':
            response = self.addprojectfiles(request)
        elif fonction == '2':
            response = self.editproject(request)
        elif fonction == '3':
            response = self.allproject(request.data)
        elif fonction == '4':
            response = self.forceupdate(request)
        elif fonction == '5':
            response = self.deleteprojectfile(request)
        elif fonction == '6':
            response = self.getpersonalprojects(request)
        elif fonction == '7':
            response = self.filterprojects(request.data)
        return Response(response)

    def defaultaddproject(self, request):
        group = WorkGroups.objects.get(id=request.data['group'])
        newProject = Projects(title=group.name + ' project', version='0.1', group=group)
        newProject.save()
        return 'Success'

    def addprojectfiles(self, request):
        # print('=====>>> '+request.data['thumbnail'])
        project = Projects.objects.get(id=request.data['id'])
        # print(project)
        filelist = request.FILES.getlist('files[]')
        i = 0
        if request.data['thumbnail'].lower() == 'true':
            thumbfile = ProjectFiles(thumbnail=True, public=True)
            projectfiles = project.files.all()
            newfile = True

            u = 0
            while u < len(projectfiles):
                # print('=====>>> ' + projectfiles[u].thumbnail)
                if projectfiles[u].thumbnail.lower() == 'true':
                    thumbfile = projectfiles[u]
                    newfile = False
                u += 1

            thumbfile.path = filelist[i]
            thumbfile.fileformat = filelist[i].name.split('.')[1]
            thumbfile.save()

            if newfile:
                project.files.add(thumbfile)
        else:
            while i < len(filelist):
                newprojectfile = ProjectFiles(path=filelist[i], fileformat=filelist[i].name.split('.')[1],
                                              thumbnail=False, public=request.data['public'].lower() == 'true')
                newprojectfile.save()

                project.files.add(newprojectfile)
                print(filelist[i])
                i += 1

        return 'success'

    def editproject(self, request):
        project = Projects.objects.get(id=request.data['id'])
        # print('=====>>> ' + str(type(project.version)))
        # print('=====>>> ' + project.version)

        dbversion = project.version.split('.')
        editversion = request.data['version'].split('.')
        versionbool = ((int(editversion[0]) > int(dbversion[0])) or (
                    int(editversion[0]) == int(dbversion[0]) and int(editversion[1]) >= int(dbversion[1])))

        if versionbool:
            data = request.data
            project.title = data['title']
            project.corevalue = data['corevalue']
            project.datasource = data['datasource']
            project.contactinfo = data['contactinfo']
            project.version = (dbversion[0] + "." + str(int(dbversion[1]) + 1))
            # print('=====>>> ' + dbversion[0] + "." + dbversion[1] + " >> " + project.version)
            project.save()
            return 'success'
        else:
            return 'outdated'

    def allproject(self, data):
        projects = Projects.objects.all()
        paginator = Paginator(projects, int(data['amount']))
        page = int(data['page'])
        paginatedhacks = paginator.page(page).object_list
        serialized = ProjectSerializer(paginatedhacks, many=True)
        return {
            'projects': serialized.data,
            'max_page': paginator.num_pages
        }

    def forceupdate(self, request):
        project = Projects.objects.get(id=request.data['id'])
        dbversion = project.version.split('.')
        data = request.data
        project.title = data['title']
        project.corevalue = data['corevalue']
        project.datasource = data['datasource']
        project.contactinfo = data['contactinfo']
        project.version = (dbversion[0] + "." + str(int(dbversion[1]) + 1))
        # print('=====>>> ' + dbversion[0] + "." + dbversion[1] + " >> " + project.version)
        project.save()
        return 'success'

    def deleteprojectfile(self, request):
        projectfile = ProjectFiles.objects.get(id=request.data['id'])
        projectfile.delete()

        return 'success'
    
    def filterprojects(self, data):
        if len(data['tags']) > 0:
            projects = Projects.objects.filter(group__event__hackathon__in=data['tags'])
        else:
            projects = Projects.objects.all()
        paginator = Paginator(projects, int(data['amount']))
        page = int(data['page'])
        
        paginatedhacks = paginator.page(page).object_list
        serialized = ProjectSerializer(paginatedhacks, many=True)
        return {
            'projects': serialized.data,
            'max_page': paginator.num_pages
        }
        pass

    def getpersonalprojects(self, request):
        authentication_classes = (TokenAuthentication,)
        permission_classes = (IsAuthenticated,)

        projects = Projects.objects.filter(group__users__id__icontains=request.user.id).distinct()

        paginator = Paginator(projects, int(request.data['amount']))
        page = int(request.data['page'])

        paginatedhacks = paginator.page(page).object_list
        serialized = ProjectSerializer(paginatedhacks, many=True)
        return {
            'projects': serialized.data,
            'max_page': paginator.num_pages
        }
        pass
