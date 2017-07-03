from flask import Blueprint, jsonify, request, Response
from membership.database.base import Session
from membership.database.models import Candidate, Election, Member, EligibleVoter, Vote, Ranking
from membership.web.auth import requires_auth
from membership.web.util import BadRequest
from membership.util.vote import STVElection
from membership.web.util import CustomEncoder, custom_jsonify
import random
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

election_api = Blueprint('election_api', __name__)


@election_api.route('/election/list', methods=['GET'])
@requires_auth(admin=False)
def get_elections(requester: Member, session: Session):
    elections = session.query(Election).all()
    elections = session.query(Election).all()
    result = {e.id: e.name for e in elections}
    return jsonify(result)


@election_api.route('/election', methods=['GET'])
@requires_auth(admin=False)
def get_election_by_id(requester: Member, session: Session):
    election = session.query(Election).get(request.args.get('id'))
    result = {'name': election.name,
              'number_winners': election.number_winners,
              'candidates': [{'id': candidate.id,
                              'name': candidate.member.name} for candidate in election.candidates],
              'status': election.status}
    return jsonify(result)


@election_api.route('/election', methods=['POST'])
@requires_auth(admin=True)
def add_election(requester: Member, session: Session):
    election = Election(name=request.json['name'])
    session.add(election)
    candidates = request.json['candidate_list'].split(',')
    members = session.query(Member).filter(Member.email_address.in_(candidates)).all()
    for member in members:
        candidate = Candidate()
        candidate.election = election
        candidate.member = member
        session.add(candidate)
    session.commit()
    return jsonify({'status': 'success'})


@election_api.route('/election/eligible/list')
@requires_auth(admin=True)
def get_eligible(requester: Member, session: Session):
    election_id = request.args['election_id']
    eligibles = session.query(EligibleVoter)\
        .filter_by(election_id=election_id).options(joinedload(EligibleVoter.member)).all()
    results = {}
    for eligible in eligibles:
        results[eligible.member_id] = {'name': eligible.member.name,
                                       'email_address': eligible.member.email_address}
    return jsonify(results)


@election_api.route('/election/<int:election_id>/vote/<int:ballot_key>', methods=['GET'])
@requires_auth(admin=False)
def get_vote(requester: Member, session: Session, election_id: int, ballot_key: int):
    vote = session.query(Vote).filter(Vote.election_id == election_id, Vote.vote_key == ballot_key).one_or_none()
    if not vote:
        return Response('Ballot #{} has not been cast for election_id={}'.format(ballot_key, election_id), 404)
    else:
        rankings = [ranking.candidate_id for ranking in vote.ranking]
        return jsonify({
            'election_id': election_id,
            'ballot_key': ballot_key,
            'rankings': rankings
        })


@election_api.route('/ballot/issue', methods=['POST'])
@requires_auth(admin=True)
def issue_ballot(requester: Member, session: Session):
    election_id = request.json['election_id']
    member_id = request.json['member_id']
    eligible = session.query(EligibleVoter). \
        filter_by(member_id=member_id, election_id=election_id).with_for_update().one_or_none()
    if not eligible:
        return BadRequest('Voter is not eligible for this election.')
    if eligible.voted:
        return BadRequest('Voter has either already voted or received a paper ballot for this '
                          'election.')
    eligible.voted = True
    session.commit()
    return jsonify({'status': 'success'})


@election_api.route('/ballot/claim', methods=['POST'])
@requires_auth(admin=True)
def add_paper_ballots(requester: Member, session: Session):
    election_id = request.json['election_id']
    number_ballots = request.json['number_ballots']
    ballot_keys = []
    for i in range(0, number_ballots):
        vote, _ = create_vote(session, election_id, 5)
        ballot_keys.append(vote.vote_key)
    return jsonify(ballot_keys)


@election_api.route('/vote/paper', methods=['POST'])
@requires_auth(admin=True)
def submit_paper_vote(requester: Member, session: Session):
    election_id = request.json['election_id']
    election = session.query(Election).get(election_id)
    if election.status == 'final':
        return BadRequest('You may not submit more votes after an election has been marked final')
    vote_key = request.json['ballot_key']
    vote = session.query(Vote).filter_by(
        election_id=election_id,
        vote_key=vote_key).with_for_update().one_or_none()

    if not vote:
        return Response('Ballot #{} for election_id={} not claimed'.format(vote_key, election_id), 404)

    if vote.ranking and not request.json.get('override', False):
        if len(vote.ranking) != len(request.json['rankings']):
            return jsonify({'status': 'mismatch'})
        for rank, candidate_id in enumerate(request.json['rankings']):
            if candidate_id != vote.ranking[rank].candidate_id:
                return jsonify({'status': 'mismatch'})
        return jsonify({'status': 'match'})
    if request.json.get('override', False):
        for rank in vote.ranking:
            session.delete(rank)
    for rank, candidate_id in enumerate(request.json['rankings']):
        ranking = Ranking(rank=rank, candidate_id=candidate_id)
        vote.ranking.append(ranking)
    session.add(vote)
    session.commit()
    return jsonify({'status': 'new'})


@election_api.route('/vote', methods=['POST'])
@requires_auth()
def submit_vote(requester: Member, session: Session):
    election_id = request.json['election_id']
    election = session.query(Election).get(election_id)
    if election.status == 'final' or election.status == 'polls closed':
        return BadRequest('You may not submit a vote after the polls have closed')
    eligible = session.query(EligibleVoter). \
        filter_by(member_id=requester.id, election_id=election_id).with_for_update().one_or_none()
    if not eligible:
        return BadRequest('You are not eligible for this election.')
    if eligible.voted:
        return BadRequest('You have either already voted or received a paper ballot for this '
                          'election.')
    eligible.voted = True
    vote, rolled_back = create_vote(session, election_id, 6)
    if rolled_back:  # If we lost the lock we have to recheck
        eligible = session.query(EligibleVoter). \
            filter_by(member_id=requester.id,
                      election_id=election_id).with_for_update().one_or_none()
        if eligible.voted:
            return BadRequest('You have either already voted or received a paper ballot for this '
                              'election.')
        eligible.voted = True
    for rank, candidate_id in enumerate(request.json['rankings']):
        ranking = Ranking(rank=rank, candidate_id=candidate_id)
        vote.ranking.append(ranking)
    session.add(vote)
    session.commit()
    return jsonify({'ballot_id': vote.vote_key})


@election_api.route('/election/voter', methods=['POST'])
@requires_auth(admin=True)
def add_voter(requester: Member, session: Session):
    election_id = request.json['election_id']
    member_id = request.json.get('member_id', requester.id)
    eligible_voter = EligibleVoter(member_id=member_id, election_id=election_id)
    session.add(eligible_voter)
    session.commit()
    return jsonify({'status': 'success'})


@election_api.route('/election/count', methods=['GET'])
@requires_auth(admin=True)
def election_count(requester: Member, session: Session):
    election_id = request.args['id']
    election = session.query(Election).get(election_id)
    stv = hold_election(election)
    winners = [session.query(Candidate).get(cid).member.name for cid in stv.winners]
    round_information = {}
    for round_number, round in enumerate(stv.previous_rounds):
        candidate_information = {}
        for cid, vote_info in round.items():
            candidate_name = session.query(Candidate).get(cid).member.name
            candidate_information[candidate_name] = vote_info
        round_information[round_number + 1] = candidate_information
    return custom_jsonify(data={'winners': winners, 'round_information': round_information},
                          encoder=CustomEncoder)


def hold_election(election: Election):
    votes = [
        [v.candidate_id for v in vote.ranking]
        for vote in election.votes if vote.ranking
    ]
    candidate_ids = [c.id for c in election.candidates]
    print("CANDIDATE_IDS: {}, VOTES: {}, NUM WINNERS: {}".format(candidate_ids, votes, election.number_winners))
    stv = STVElection([c.id for c in election.candidates], election.number_winners, votes)
    stv.hold_election()
    return stv


def create_vote(session, election_id, digits):
    i = 0
    rolled_back = False
    while i < 5:
        try:
            a = random.randint(10 ** (digits - 1), 10 ** digits - 1)
            v = Vote(vote_key=a, election_id=election_id)
            session.add(v)
            session.commit()
            return v, rolled_back
        except IntegrityError:
            print('Had to retry')
            i += 1
            session.rollback()
            rolled_back = True
    raise Exception('Failing to find a random key in five tries. Think something is wrong.')
