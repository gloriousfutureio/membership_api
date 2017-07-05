from typing import Any, Dict, Iterable

import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType
from graphql.execution.base import ResolveInfo
from sqlalchemy.orm.query import Query

from membership.database import models
from membership.database.base import Base
from membership.database.models import *


# Full database models

class MemberSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Member


class CommitteeSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Committee


class RoleSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Role


class MeetingSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Meeting


class AttendeeSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Attendee


class ElectionSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Election


class CandidateSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Candidate


class VoteSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Vote


class RankingSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Ranking


class EligibleVoterSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.EligibleVoter


# API View Models

class AnonMemberFields(graphene.AbstractType):
    id = graphene.String()
    eligible_votes = graphene.List(EligibleVoterSchema)
    meetings_attended = graphene.List(MeetingSchema)


class AnonMemberSchema(graphene.ObjectType, AnonMemberFields):
    pass


class QuerySchema(graphene.ObjectType):
    all_attendees = graphene.List(AttendeeSchema)
    all_candidates = graphene.List(CandidateSchema)
    all_committees = graphene.List(CommitteeSchema)
    all_elections = graphene.List(ElectionSchema)
    all_eligible_voters = graphene.List(EligibleVoterSchema)
    all_meetings = graphene.List(MeetingSchema)
    all_members = graphene.List(MemberSchema)
    all_rankings = graphene.List(RankingSchema)
    all_roles = graphene.List(RoleSchema)
    all_votes = graphene.List(VoteSchema)

    anon_members = graphene.List(AnonMemberSchema)

    my_user = graphene.Field(MemberSchema)
    my_meetings = graphene.List(MeetingSchema)

    def resolve_all_attendees(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = AttendeeSchema.get_query(context)
        return query.all()

    def resolve_all_candidates(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = CandidateSchema.get_query(context)
        return query.all()

    def resolve_all_committees(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = CommitteeSchema.get_query(context)
        return query.all()

    def resolve_all_elections(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = ElectionSchema.get_query(context)
        return query.all()

    def resolve_all_eligible_voters(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = EligibleVoterSchema.get_query(context)
        return query.all()

    def resolve_all_meetings(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = MeetingSchema.get_query(context)
        return query.all()

    def resolve_all_members(self, args: dict, context: dict, info: ResolveInfo):
        requester: Member = context['requester']
        if requester.is_admin():
            query: Query = MemberSchema.get_query(context)
            return query.all()
        else:
            return [requester]

    def resolve_anon_members(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = MemberSchema.get_query(context)
        filters = filters_for(Member, args)
        all: Iterable[Member] = query.filter(*filters)
        result: Iterable[AnonMemberSchema] = [AnonMemberSchema(
            id=m.id,
            eligible_votes=m.eligible_votes,
            meetings_attended=m.meetings_attended
        ) for m in all]
        return result

    def resolve_all_rankings(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = RankingSchema.get_query(context)
        return query.all()

    def resolve_all_roles(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = RoleSchema.get_query(context)
        return query.all()

    def resolve_all_votes(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = VoteSchema.get_query(context)
        return query.all()

    def resolve_my_user(self, args: dict, context: dict, info: ResolveInfo):
        requester: Member = context['requester']
        return requester

    def resolve_my_meetings(self, args: dict, context: dict, info: ResolveInfo):
        print('args = {}'.format(args))
        print('resolve info = {}'.format(info))
        requester: Member = context['requester']
        query: Query = MeetingSchema.get_query(context)
        return query.filter(requester.id in Meeting.attendees)


def filters_for(model: Base, args: Dict[str, Any]):
    return [getattr(model, k) == v for k, v in args.items() if v is not None]


schema = graphene.Schema(query=QuerySchema)
