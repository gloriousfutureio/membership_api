import typing
from typing import Any, Callable, Dict, Generic, Iterable, Type, T

import graphene as g
from graphene.types.datetime import DateTime
from graphene_sqlalchemy import SQLAlchemyObjectType
from graphql.execution.base import ResolveInfo
from graphql.language.ast import IntValue, StringValue
from sqlalchemy.orm.query import Query

from membership.database import models
from membership.database.models import *


# Full database models

class MemberSchema(SQLAlchemyObjectType):
    class Meta:
        model = models.Member

    name = g.String()

    def resolve_name(self):
        return Member.name.getter(self)


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

def _reltype(classname: str) -> str:
    return 'membership.schemas.graphql.' + classname


class Connector(Callable[[T], Any]):

    def __init__(self, t: Type[T], f: Callable[[T], Any]):
        self.connect = f
        self.type = t

    def __call__(self, value: T) -> Any:
        return self.connect(value)


def connector(type: Type[T]):
    def decorator(f: Callable[[T], Any]):
        return Connector(type, f)
    return decorator

M = typing.TypeVar('M', bound=Base)
S = typing.TypeVar('S', bound=g.ObjectType)


def connect(schema_cls: Type[S], model_cls: Type[M], instance: M) -> S:
    # Try to find a custom connector with a matching type
    connectors = [
        c for c in (
            getattr(schema_cls, k) for k, c in vars(schema_cls).items()
            if isinstance(c, staticmethod) and isinstance(getattr(schema_cls, k), Connector)
            or isinstance(c, Connector)
        ) if issubclass(c.type, model_cls)
    ]
    if connectors:
        if len(connectors) > 1:
            raise Exception('Multiple connectors with the matching type {} for {}'.format(model_cls, schema_cls))
        t_connector = connectors[0]
        return t_connector(instance)
    # Otherwise, try to match fields to standard types and recurse
    model_members: Dict[str, Any] = {k: getattr(instance, k) for k in vars(model_cls) if not k.startswith('_')}
    schema_types: Dict[str, g.Field] = {k: t for k, t in schema_cls._meta.fields.items() if not k.startswith('_')}
    model_args: Dict[str, Any] = {k: v for k, v in model_members.items() if k in schema_types}
    missing_schema_args: Dict[str, g.Field] = {k: t for k, t in schema_types.items() if k not in model_args}
    if missing_schema_args:
        raise Exception('Schema type "{}" requires the following missing members from model type {}: {}'.format(
            schema_cls.__name__,
            model_cls.__name__,
            ', '.join('{}: {}'.format(k, t.type) for k, t in missing_schema_args.items())
        ))
    else:
        # recursively fill out the fields
        kwargs = {}
        for k, schema_type in schema_types.items():
            t = schema_type.type
            model_value = model_args.get(k)
            # Handle and unwrap NonNull types
            if isinstance(t, g.NonNull):
                if model_value is None:
                    raise Exception('Cannot return None value for NonNull value of schema {}.{}: {}'.format(
                        schema_cls.__name__,
                        k,
                        schema_type
                    ))
                t = t.of_type
                t_cls = t
            else:
                t_cls = type(t)
            # Handle unwrapped type
            if issubclass(t_cls, g.Scalar):
                v = model_args[k]
            elif issubclass(t_cls, g.ObjectType):
                v = connect(t_cls, type(model_value), model_value)
            elif issubclass(t_cls, g.List):
                v = [connect(t.of_type, type(item), item) for item in model_value]
            else:
                raise Exception('Cannot connect model value to recognized graphene schema type "{}". '
                                'Expected combatible type for {}'.format(t_cls, model_value))
            kwargs[k] = v
        ast = schema_cls(**kwargs)
        return ast


class ID(g.Scalar):
    """
    Parses input string or number as an integer.

    This allows the UI to pass strings and not worry about the id encoded in the database.
    """

    serialize = str
    parse_value = int

    @staticmethod
    def parse_literal(ast):
        if isinstance(ast, (StringValue, IntValue)):
            return int(ast.value)


class EntityFields(g.AbstractType):
    """
    The root of every identifiable entity in the system.

    Provides the id field.
    """
    id = g.NonNull(ID)


class PubElectionSchema(g.ObjectType, EntityFields):
    name = g.NonNull(g.String)
    status = g.NonNull(g.String)
    number_winners = g.NonNull(g.Int)

    candidates = g.List(_reltype('PubCandidateSchema'))
    votes = g.List(_reltype('PubVoteSchema'))


class PubCandidateSchema(g.ObjectType, EntityFields):
    member_id = g.Int()
    election_id = g.Int()
    name = g.String()
    biography = g.String()

    election = g.Field(_reltype('PubElectionSchema'))

    @staticmethod
    @connector(Candidate)
    def connect_candidate(candidate: Candidate) -> 'PubCandidateSchema':
        return PubCandidateSchema(
            id=candidate.id,
            member_id=candidate.member_id,
            election_id=candidate.election_id,
            name=candidate.member.name,
            biography=candidate.member.biography,
            election=connect(PubElectionSchema, Election, candidate.election),
        )


class PubVoteSchema(g.ObjectType, EntityFields):
    vote_key = g.Int()
    election_id = ID()

    election = g.Field(_reltype('PubElectionSchema'))
    ranking = g.List(_reltype('PubRankingSchema'))

    ranked_candidates = g.List(_reltype('PubCandidateSchema'))


class PubRankingSchema(g.ObjectType, EntityFields):
    vote_id = ID()
    rank = g.Int()
    candidate_id = ID()

    vote = g.Field(_reltype('PubVoteSchema'))
    candidate = g.Field(_reltype('PubCandidateSchema'))


class PubCommitteeSchema(g.ObjectType, EntityFields):
    name = g.String()


class PubMeetingSchema(g.ObjectType, EntityFields):
    short_id = ID()
    name = g.String()
    committee_id = ID()
    start_time = DateTime()
    end_time = DateTime()

    attendees = g.List(_reltype('PubAttendeeSchema'))


class PubAttendeeSchema(g.ObjectType, EntityFields):
    meeting_id = ID()
    member_id = ID()

    meeting = g.Field(_reltype('PubMeetingSchema'))


class MyEligibleVoterSchema(g.ObjectType, EntityFields):
    voted = g.Boolean()
    election_id = ID()

    election = g.Field(_reltype('PubElectionSchema'))


class MyRole(g.ObjectType, EntityFields):
    committee_id = ID()
    name = g.NonNull(g.String)

    committee = g.Field(_reltype('PubCommitteeSchema'))


class MyUserSchema(g.ObjectType, EntityFields):
    first_name = g.String()
    last_name = g.String()
    email_address = g.String()
    biography = g.String()

    eligible_votes = g.List(_reltype('MyEligibleVoterSchema'))
    meetings_attended = g.List(_reltype('PubMeetingSchema'))
    roles = g.List(_reltype('MyRole'))


class QuerySchema(g.ObjectType):
    all_attendees = g.List(AttendeeSchema)
    all_candidates = g.List(CandidateSchema)
    all_committees = g.List(CommitteeSchema)
    all_elections = g.List(ElectionSchema)
    all_eligible_voters = g.List(EligibleVoterSchema)
    all_meetings = g.List(MeetingSchema)
    all_members = g.List(MemberSchema)
    all_rankings = g.List(RankingSchema)
    all_roles = g.List(RoleSchema)
    all_votes = g.List(VoteSchema)

    public_elections = g.List(PubElectionSchema)

    my_user = g.Field(MemberSchema)
    my_meetings = g.List(MeetingSchema)

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

    def resolve_public_elections(self, args: dict, context: dict, info: ResolveInfo):
        query: Query = ElectionSchema.get_query(context)
        # filters = filters_for(Member, args)
        all: List[Election] = query.all()
        result: List[PubElectionSchema] = [connect(PubElectionSchema, Election, e) for e in all]
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


schema = g.Schema(query=QuerySchema)
