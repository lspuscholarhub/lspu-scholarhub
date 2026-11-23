"""The unbatched panel and the batch list must resolve campus like the guards do.

An approved scholar whose application row carries no campus stamp still belongs
to their applicant's campus, and a batch with no campus of its own still belongs
to its program's campus. Verify sections 7 and 12 pin both.
"""
from app import db
from app.models import ScholarshipApplication, ScholarshipBatch


def test_panel_lists_then_clears_an_unbatched_scholar(open_batch, seed, approve, sign_in,
                                                      unbatched_panel):
    """Section 7: an approved scholar with no batch is listed, then clears."""
    stray = approve(seed.student, seed.program)
    client = sign_in(seed.admin)
    name = seed.student.get_full_name()

    response = client.get('/admin/batches')
    assert response.status_code == 200
    panel = unbatched_panel(response.get_data(as_text=True))
    assert panel, 'the unbatched panel was not rendered'
    assert name in panel
    assert 'Unbatched' in panel

    client.post(f'/admin/batches/{open_batch.id}/assign',
                data={'app_ids': [str(stray.id)]})

    response = client.get('/admin/batches')
    assert response.status_code == 200
    assert name not in unbatched_panel(response.get_data(as_text=True))
    db.session.expire_all()
    assert db.session.get(ScholarshipApplication, stray.id).batch_id == open_batch.id


def test_panel_resolves_the_applicants_campus(seed, approve, sign_in, unbatched_panel):
    """Section 12: an unstamped application is listed for the applicant's campus."""
    ours = approve(seed.student, seed.program, campus_id=None)
    theirs = approve(seed.other_student, seed.program, campus_id=None)
    client = sign_in(seed.admin)

    response = client.get('/admin/batches')
    assert response.status_code == 200
    panel = unbatched_panel(response.get_data(as_text=True))
    assert panel, 'the unbatched panel was not rendered'
    assert seed.student.get_full_name() in panel
    assert seed.other_student.get_full_name() not in panel

    seed.other_student.campus_id = seed.campus.id
    db.session.commit()

    panel = unbatched_panel(client.get('/admin/batches').get_data(as_text=True))
    assert seed.other_student.get_full_name() in panel
    assert ours.batch_id is None and theirs.batch_id is None


def test_staff_batch_list_resolves_campus_through_the_program(seed, sign_in):
    """Section 12: the staff list shows an unpinned batch and hides a foreign one."""
    db.session.add_all([
        ScholarshipBatch(scholarship_id=seed.program.id,
                         academic_period_id=seed.period.id,
                         batch_name='Fallback Batch', batch_number=1,
                         status='open', campus_id=None),
        ScholarshipBatch(scholarship_id=seed.program.id,
                         academic_period_id=seed.period.id,
                         batch_name='Foreign Batch', batch_number=2,
                         status='open', campus_id=seed.other_campus.id),
    ])
    db.session.commit()

    client = sign_in(seed.staff)
    url = f'/staff/batches?scholarship_id={seed.program.id}'

    body = client.get(url).get_data(as_text=True)
    assert 'Fallback Batch' in body
    assert 'Foreign Batch' not in body

    foreign = ScholarshipBatch.query.filter_by(batch_name='Foreign Batch').one()
    foreign.campus_id = seed.campus.id
    db.session.commit()

    body = client.get(url).get_data(as_text=True)
    assert 'Foreign Batch' in body
