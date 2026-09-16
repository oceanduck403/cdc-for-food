"""Exercise real API, persistence and access boundaries for article interaction."""
import pytest
from app.core.security import admin_auth_fingerprint, create_access_token, hash_password
from app.models.user import User
from app.models.knowledge import KnowledgeArticle

pytestmark = pytest.mark.asyncio


def auth(user):
    extra = {'role': user.role}
    if user.role == 'admin':
        extra['admin_auth'] = admin_auth_fingerprint(user)
    return {'Authorization': 'Bearer ' + create_access_token(str(user.id), extra=extra)}


async def test_article_reactions_comments_notifications_and_ownership(client, db):
    author = User(role='patient', nickname='甲')
    reader = User(role='patient', nickname='乙')
    stranger = User(role='patient', nickname='丙')
    article = KnowledgeArticle(category='guide', title='均衡膳食测试文章', summary='饮食建议', content_html='<p>健康知识</p>')
    db.add_all([author, reader, stranger, article]); await db.commit()
    await db.refresh(author); await db.refresh(reader); await db.refresh(stranger); await db.refresh(article)
    base = '/api/v1/community'
    aid = article.id

    # Public reading, private actions and per-user state.
    public = await client.get(f'{base}/articles/{aid}')
    assert public.status_code == 200 and public.json()['liked'] is False
    assert (await client.put(f'{base}/articles/{aid}/reactions/like', json={'active': True})).status_code == 401
    assert (await client.get(base + '/favorites')).status_code == 401
    assert (await client.get(base + '/notifications')).status_code == 401
    a = await client.put(f'{base}/articles/{aid}/reactions/like', headers=auth(author), json={'active': True})
    assert a.status_code == 200, a.text
    assert a.json()['likeCount'] == 1 and a.json()['liked'] is True
    again = await client.put(f'{base}/articles/{aid}/reactions/like', headers=auth(author), json={'active': True})
    assert again.status_code == 200 and again.json()['likeCount'] == 1
    assert (await client.get(f'{base}/articles/{aid}', headers=auth(reader))).json()['liked'] is False
    await client.put(f'{base}/articles/{aid}/reactions/favorite', headers=auth(author), json={'active': True})
    assert [i['id'] for i in (await client.get(base + '/favorites', headers=auth(author))).json()['items']] == [aid]
    assert (await client.get(base + '/favorites', headers=auth(reader))).json()['items'] == []

    body = {'content': '清淡饮食很实用', 'request_id': 'comment-request-001'}
    created = await client.post(f'{base}/articles/{aid}/comments', headers=auth(author), json=body)
    assert created.status_code == 200, created.text
    cid = created.json()['id']
    assert (await client.post(f'{base}/articles/{aid}/comments', headers=auth(author), json=body)).json()['id'] == cid
    assert (await client.post(f'{base}/articles/{aid}/comments', headers=auth(author), json={**body, 'content':'改变内容'})).status_code == 409
    assert (await client.post(f'{base}/articles/{aid}/comments', headers=auth(reader), json={'content':'  ', 'request_id':'blank-comment-01'})).status_code == 422
    assert (await client.post(f'{base}/articles/{aid}/comments', headers=auth(reader), json={'content':'x'*501, 'request_id':'long-comment-01'})).status_code == 422

    reply = await client.post(f'{base}/articles/{aid}/comments', headers=auth(reader), json={
        'content':'同意，这个建议好', 'parent_id':cid, 'request_id':'reply-request-001'})
    assert reply.status_code == 200, reply.text
    rid = reply.json()['id']
    comments = (await client.get(f'{base}/articles/{aid}/comments')).json()['items']
    assert len(comments) == 2 and comments[0]['replyTo'] == '甲'
    assert (await client.put(f'{base}/comments/{cid}/like', headers=auth(reader), json={'active':True})).json()['likeCount'] == 1
    assert (await client.put(f'{base}/comments/{cid}/like', headers=auth(reader), json={'active':True})).json()['likeCount'] == 1
    assert (await client.get(base + '/notifications?kind=received', headers=auth(author))).json()['items'][0]['kind'] == 'comment_like'
    assert (await client.get(base + '/notifications?kind=received', headers=auth(stranger))).json()['items'] == []
    assert (await client.delete(f'{base}/comments/{cid}', headers=auth(reader))).status_code == 403
    notices = (await client.get(base + '/notifications', headers=auth(author))).json()['items']
    assert any(n['kind'] == 'reply' and n['commentId'] == rid for n in notices)
    assert (await client.post(f'{base}/notifications/{notices[0]["id"]}/read', headers=auth(stranger))).status_code == 404
    assert (await client.post(base + '/notifications/read-all', headers=auth(author))).status_code == 200
    assert (await client.get(base + '/notifications/unread', headers=auth(author))).json()['count'] == 0

    assert (await client.delete(f'{base}/comments/{cid}', headers=auth(author))).status_code == 200
    remaining = (await client.get(f'{base}/articles/{aid}/comments')).json()['items']
    assert len(remaining) == 1 and remaining[0]['parentContent'] == '原评论已删除'
    assert (await client.put(f'{base}/comments/{cid}/like', headers=auth(reader), json={'active':True})).status_code == 404
    assert (await client.put(f'{base}/articles/{aid}/reactions/like', headers=auth(author), json={'active':False})).json()['likeCount'] == 0
    await client.put(f'{base}/articles/{aid}/reactions/favorite', headers=auth(author), json={'active':False})
    assert (await client.get(base + '/favorites', headers=auth(author))).json()['items'] == []


async def test_article_cursor_and_comment_cross_article_validation(client, db):
    user = User(role='patient', nickname='分页者')
    a = KnowledgeArticle(category='nutrition', title='A', summary='a')
    b = KnowledgeArticle(category='nutrition', title='B', summary='b')
    db.add_all([user, a, b]); await db.commit()
    await db.refresh(user); await db.refresh(a); await db.refresh(b)
    base = '/api/v1/community'
    page = (await client.get(base + '/articles?category=nutrition&limit=1')).json()
    assert page['hasMore'] is True
    next_page = (await client.get(base + f'/articles?category=nutrition&limit=1&before={page["nextCursor"]}')).json()
    assert next_page['items'][0]['id'] != page['items'][0]['id']
    original = (await client.post(f'{base}/articles/{a.id}/comments', headers=auth(user), json={'content':'文章A', 'request_id':'cross-article-001'})).json()['id']
    invalid = await client.post(f'{base}/articles/{b.id}/comments', headers=auth(user), json={'content':'错误回复', 'parent_id':original, 'request_id':'cross-article-002'})
    assert invalid.status_code == 400


async def test_comment_report_and_admin_moderation(client, db):
    author = User(role='patient', nickname='发言者')
    reporter = User(role='patient', nickname='举报者')
    admin = User(role='admin', nickname='管理员', username='community_admin', password_hash=hash_password('Admin-test-123'))
    article = KnowledgeArticle(category='guide', title='评论审核测试', summary='健康知识')
    db.add_all([author, reporter, admin, article]); await db.commit()
    for item in (author, reporter, admin, article):
        await db.refresh(item)
    base = '/api/v1/community'
    created = await client.post(f'{base}/articles/{article.id}/comments', headers=auth(author),
                                json={'content':'测试中的不实信息', 'request_id':'report-test-001'})
    assert created.status_code == 200, created.text
    cid = created.json()['id']
    report_url = f'{base}/comments/{cid}/report'
    assert (await client.post(report_url, json={'reason':'不实信息'})).status_code == 401
    assert (await client.post(report_url, headers=auth(author), json={'reason':'不实信息'})).status_code == 400
    assert (await client.post(report_url, headers=auth(reporter), json={'reason':'其他'})).status_code == 422
    reported = await client.post(report_url, headers=auth(reporter), json={'reason':'不实信息'})
    assert reported.status_code == 200, reported.text
    assert (await client.post(report_url, headers=auth(reporter), json={'reason':'不实信息'})).status_code == 200
    assert (await client.get(f'{base}/moderation/reports', headers=auth(reporter))).status_code == 403
    pending = await client.get(f'{base}/moderation/reports', headers=auth(admin))
    assert pending.status_code == 200, pending.text
    assert len(pending.json()) == 1 and pending.json()[0]['commentId'] == cid
    report_id = pending.json()[0]['id']
    moderate_url = f'{base}/moderation/reports/{report_id}'
    assert (await client.post(moderate_url, headers=auth(reporter), json={'action':'hide'})).status_code == 403
    hidden = await client.post(moderate_url, headers=auth(admin), json={'action':'hide'})
    assert hidden.status_code == 200, hidden.text
    assert (await client.get(f'{base}/articles/{article.id}/comments')).json()['items'] == []
    assert (await client.get(f'{base}/moderation/reports', headers=auth(admin))).json() == []
    assert (await client.post(report_url, headers=auth(reporter), json={'reason':'不实信息'})).status_code == 404


async def test_comment_maps_content_security_results(client, db, monkeypatch):
    from app.api.v1 import community
    from app.services.wechat_content_security import ContentSecurityRejected, ContentSecurityUnavailable

    user = User(role='patient', nickname='审核用户', openid='openid-security-test')
    article = KnowledgeArticle(category='guide', title='发布前审核', summary='健康知识')
    db.add_all([user, article]); await db.commit()
    await db.refresh(user); await db.refresh(article)

    async def rejected(_content, _openid):
        raise ContentSecurityRejected('评论含有不适合公开展示的内容，请修改后再试')

    monkeypatch.setattr(community, 'check_public_text', rejected)
    url = f'/api/v1/community/articles/{article.id}/comments'
    bad = await client.post(url, headers=auth(user), json={
        'content': '待审核文本', 'request_id': 'security-reject-001'
    })
    assert bad.status_code == 400
    assert '修改后再试' in bad.json()['detail']

    async def unavailable(_content, _openid):
        raise ContentSecurityUnavailable('微信内容安全服务暂时不可用')

    monkeypatch.setattr(community, 'check_public_text', unavailable)
    retry = await client.post(url, headers=auth(user), json={
        'content': '正常健康评论', 'request_id': 'security-retry-001'
    })
    assert retry.status_code == 503
