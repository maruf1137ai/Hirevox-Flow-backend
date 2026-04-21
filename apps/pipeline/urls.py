from django.urls import path

from . import views


urlpatterns = [
    path("board/", views.board, name="pipeline-board"),
    path("move/", views.move, name="pipeline-move"),
]
