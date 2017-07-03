import graphene
from graphene_sqlalchemy import SQLAlchemyObjectType

from membership.database import models


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


class Query(graphene.ObjectType):
    attendees = graphene.List(AttendeeSchema)
    candidates = graphene.List(CandidateSchema)
    committees = graphene.List(CommitteeSchema)
    elections = graphene.List(ElectionSchema)
    eligible_voters = graphene.List(EligibleVoterSchema)
    meetings = graphene.List(MeetingSchema)
    members = graphene.List(MemberSchema)
    rankings = graphene.List(RankingSchema)
    roles = graphene.List(RoleSchema)
    votes = graphene.List(VoteSchema)

    def resolve_attendees(self, args, context, info):
        query = AttendeeSchema.get_query(context)
        return query.all()

    def resolve_candidates(self, args, context, info):
        query = CandidateSchema.get_query(context)
        return query.all()

    def resolve_committees(self, args, context, info):
        query = CommitteeSchema.get_query(context)
        return query.all()

    def resolve_elections(self, args, context, info):
        query = ElectionSchema.get_query(context)
        return query.all()

    def resolve_eligible_voters(self, args, context, info):
        query = EligibleVoterSchema.get_query(context)
        return query.all()

    def resolve_meetings(self, args, context, info):
        query = MeetingSchema.get_query(context)
        return query.all()

    def resolve_members(self, args, context, info):
        query = MemberSchema.get_query(context)
        return query.all()

    def resolve_rankings(self, args, context, info):
        query = RankingSchema.get_query(context)
        return query.all()

    def resolve_roles(self, args, context, info):
        query = RoleSchema.get_query(context)
        return query.all()

    def resolve_votes(self, args, context, info):
        query = VoteSchema.get_query(context)
        return query.all()


schema = graphene.Schema(query=Query)
