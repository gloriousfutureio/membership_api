from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from membership.database.base import Base


class Committee(Base):
    __tablename__ = 'committees'

    id: int = Column(Integer, primary_key=True, unique=True)
    name: str = Column(String(45))


class Member(Base):
    __tablename__ = 'members'

    id: int = Column(Integer, primary_key=True, unique=True)
    first_name: str = Column(String(45))
    last_name: str = Column(String(45))
    email_address: str = Column(String(254), unique=True)
    biography: str = Column(String(10000))

    eligible_votes: 'List[EligibleVoter]' = relationship('EligibleVoter', back_populates='member')
    meetings_attended: 'List[Attendee]' = relationship('Attendee', back_populates='member')
    roles: 'List[Role]' = relationship('Role', back_populates='member')

    @property
    def name(self):
        n = ''
        if self.first_name:
            n = self.first_name
        if self.last_name:
            n += ' ' + self.last_name
        return n

    def has_committee_role(self, committee: Optional[Union[Committee, int]], role: str):
        committee_id = committee.id if isinstance(committee, Committee) else committee
        return any(mr.committee_id == committee_id and mr.role == role for mr in self.roles)

    def is_admin(self):
        return self.has_committee_role(committee=None, role='admin')


class Role(Base):
    __tablename__ = 'roles'

    id: int = Column(Integer, primary_key=True, unique=True)
    committee_id: int = Column(ForeignKey('committees.id'))
    member_id: int = Column(ForeignKey('members.id'))
    role: str = Column(String(45))

    committee: 'Committee' = relationship(Committee)
    member: 'Member' = relationship('Member', back_populates='roles')


class Meeting(Base):
    __tablename__ = 'meetings'

    id: int = Column(Integer, primary_key=True, unique=True)
    short_id: int = Column(Integer, nullable=False, unique=True)
    name: str = Column(String(255), nullable=False)
    committee_id: int = Column(ForeignKey('committees.id'))
    start_time: datetime = Column(DateTime)
    end_time: datetime = Column(DateTime)

    attendees: 'List[Attendee]' = relationship('Attendee', back_populates='meeting')


class Attendee(Base):
    __tablename__ = 'attendees'

    id: int = Column(Integer, primary_key=True, unique=True)
    meeting_id: int = Column(ForeignKey('meetings.id'))
    member_id: int = Column(ForeignKey('members.id'))

    member: 'Member' = relationship('Member', back_populates='meetings_attended')
    meeting: 'Meeting' = relationship('Meeting', back_populates='attendees')


class Election(Base):
    __tablename__ = 'elections'

    id: int = Column(Integer, primary_key=True, unique=True)
    name: str = Column(String(45), nullable=False)
    status: str = Column(String(45), nullable=False, default='draft')
    number_winners: int = Column(Integer)

    candidates: 'List[Candidate]' = relationship('Candidate', back_populates='election')
    votes: 'List[Vote]' = relationship('Vote', back_populates='election')
    voters: 'List[EligibleVoter]' = relationship('EligibleVoter', back_populates='election')


class Candidate(Base):
    __tablename__ = 'candidates'

    id: int = Column(Integer, primary_key=True, unique=True)
    member_id: int = Column(ForeignKey('members.id'))
    election_id: int = Column(ForeignKey('elections.id'))

    member: 'Member' = relationship(Member)
    election: 'Election' = relationship('Election', back_populates='candidates')


class Vote(Base):
    __tablename__ = 'votes'
    __table_args__ = (UniqueConstraint('vote_key', 'election_id'),)

    id: int = Column(Integer, primary_key=True, unique=True)
    vote_key: int = Column(Integer)
    election_id: int = Column(ForeignKey('elections.id'))

    election: 'Election' = relationship('Election', back_populates='votes')
    ranking: 'List[Ranking]' = relationship('Ranking', back_populates='vote', order_by='Ranking.rank')


class Ranking(Base):
    __tablename__ = 'rankings'

    id: int = Column(Integer, primary_key=True, unique=True)
    vote_id: int = Column(ForeignKey('votes.id'))
    rank: int = Column(Integer)
    candidate_id: int = Column(ForeignKey('candidates.id'))

    vote: 'Vote' = relationship('Vote', back_populates='ranking')
    candidate: 'Candidate' = relationship('Candidate')


class EligibleVoter(Base):
    __tablename__ = 'eligible_voters'

    id: int = Column(Integer, primary_key=True, unique=True)
    member_id: int = Column(ForeignKey('members.id'))
    voted: bool = Column(Boolean)
    election_id: int = Column(ForeignKey('elections.id'))

    member: 'Member' = relationship('Member', back_populates='eligible_votes')
    election: 'Election' = relationship('Election', back_populates='voters')
