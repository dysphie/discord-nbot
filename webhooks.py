from discord import TextChannel, Webhook, RequestsWebhookAdapter

from db import webhooks


def get_webhook_for_channel(channel: TextChannel) -> Webhook:
    model = webhooks.find_one({'_id': channel.id})
    if not model:
        webhook: Webhook = await channel.create_webhook(name='NBot %s' % channel.name)
        model = {
            '_id': channel.id,
            'id': webhook.id,
            'token': webhook.token
        }
        webhooks.insert(model)
    return Webhook.partial(model['id'], model['token'], adapter=RequestsWebhookAdapter())
