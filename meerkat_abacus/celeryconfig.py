"""
Celery configuration file
"""
import meerkat_abacus.config as config
import os



BROKER_URL = 'amqp://guest@dev_rabbit_1//'
CELERY_RESULT_BACKEND = 'rpc://guest@dev_rabbit_1//'

new_url = os.environ.get("MEERKAT_BROKER_URL")
if new_url:
    BROKER_URL = new_url
    CELERY_RESULT_BACKEND = new_url

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
#CELERY_TIMEZONE = 'Europe/Oslo'
CELERY_ENABLE_UTC = True

from datetime import timedelta

CELERYBEAT_SCHEDULE = {}
if config.start_celery: 
    if config.fake_data:
        CELERYBEAT_SCHEDULE['generate-fake-data'] = {
                'task': 'task_queue.add_new_fake_data',
                'schedule': timedelta(seconds=config.interval),
                'args': (5,)
            }

    CELERYBEAT_SCHEDULE['add_new_data']= {
            'task': 'task_queue.import_new_data',
            'schedule': timedelta(seconds=config.interval)
        }

    CELERYBEAT_SCHEDULE['new_data_to_codes'] = {
            'task': 'task_queue.new_data_to_codes',
            'schedule': timedelta(seconds=config.interval)
        }
    
    CELERYBEAT_SCHEDULE['new_links'] = {
            'task': 'task_queue.add_new_links',
            'schedule': timedelta(seconds=config.interval)
        }

    
