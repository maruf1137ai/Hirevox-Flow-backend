from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Notification
from .serializers import NotificationSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    qs = Notification.objects.filter(user=request.user)[:50]
    unread = Notification.objects.filter(user=request.user, read=False).count()
    return Response({
        "results": NotificationSerializer(qs, many=True).data,
        "unread_count": unread,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    count = Notification.objects.filter(user=request.user, read=False).count()
    return Response({"unread_count": count})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mark_read(request, pk):
    notif = Notification.objects.filter(user=request.user, id=pk).first()
    if not notif:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    notif.read = True
    notif.save(update_fields=["read"])
    return Response(NotificationSerializer(notif).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    return Response({"detail": "All notifications marked as read."})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_notification(request, pk):
    Notification.objects.filter(user=request.user, id=pk).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
