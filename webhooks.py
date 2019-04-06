from discord import TextChannel, Webhook, RequestsWebhookAdapter

from db import webhooks


async def send_webhook_to_channel(channel: TextChannel, content: str, nickname: str, avatar_url: str):
    model = webhooks.find_one({'_id': channel.id})
    if not model:
        webhook: Webhook = await channel.create_webhook(name='NBot %s' % channel.name)
        model = {
            '_id': channel.id,
            'id': webhook.id,
            'token': webhook.token
        }
        webhooks.insert(model)
    else:
        webhook = Webhook.partial(model['id'], model['token'], adapter=RequestsWebhookAdapter())
    await webhook.send(content=content, username=nickname, avatar_url=avatar_url)
