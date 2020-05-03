"""Django tasks for celery."""

from datetime import datetime
from celery import shared_task

from celery import Celery

from .models import Project, TMS
from .models import parse_projects_for_TMS
import TMSlib.TMS as TMSlib
from django.contrib.auth.models import User

import eta_tasks
import logging
import email_reports


@shared_task
def estimate_all():
    """Estimate ETA for all tasks."""
    tms_set = TMS.objects.all()
    logging.info(
        'starting generating ETAs for the \
following TMS entries ({}): {}'.format(
            len(tms_set), tms_set))
    for tms in tms_set:
        logging.info('generating ETAs for TMS {}'.format(tms))
        try:
            project_set = Project.objects.all().filter(project_tms_id=tms.id)
            if project_set:
                logging.info('generating ETAs for TMS {} Projects: {}'.format(
                    tms, project_set))
                try:
                    tms_wrapper = TMSlib.TMSWrapper(tms)
                    tms_wrapper.init_ETApredict(project_set)
                    tms_wrapper.estimate_tasks()
                    raw_status_report = tms_wrapper.generate_projects_status_report()
                    email_msg = email_reports.EmailReportProcess.format_email_msg(
                        tms.owner, raw_status_report)
                    #Send email
                    email_reports.EmailReportProcess.send_email(email_msg)

                    del tms_wrapper

                    # eta_tasks.generate_email_report(tms, project_set, tms.owner)
                except Exception as e:
                    logging.error('Could not generate ETAs for TMS {} \
    Projects {} due to "{}"'.format(tms, project_set, e))
            else:
                logging.info('no projects found for TMS {}'.format(tms))
        except Exception as e2:
            logging.info('Could not generate ETAs for TMS {} due to'.format(
                tms, e2))
    return True

def get_tms_by_id(tms_id):
    logging.info('searching for TMS with id: {}'.format(tms_id))
    tms_list = TMS.objects.all().filter(
            pk=tms_id)
    logging.info('found TMSs: {}'.format(tms_list))
    if len(tms_list) > 1:
        raise NameError('TMS id "{}" is not unique'.format(tms_id))
    elif tms_list is None or len(tms_list) == 0:
        logging.warning('no TMS found with id {}'.format(tms_id))
        return None
    else:
        tms = tms_list[0]
    return tms

@shared_task
def estimate_ETA_for_TMS_project_set_ids(
        tms_id,
        projects_set_ids,
        params):
    """Generate ETAs for a given TMS and set of projects."""
    tms = get_tms_by_id(tms_id)
    if tms is None:
        raise NameError('cannot find TMS with id {}'.format(tms_id))
    projects_set = Project.objects.all().filter(pk__in=projects_set_ids)
    logging.info('found projects_set: {}'.format(projects_set))
    if 'simulate_failure' in params:
        raise NameError('Simulating failure')
    eta_tasks.estimate_ETA_for_TMS(tms, projects_set, **params)

@shared_task
def parse_projects_for_tms_id(
        tms_id,
        params):
    """Parse projects for the given TMS id."""
    tms = get_tms_by_id(tms_id)
    if tms is None:
        raise NameError('cannot find TMS with id {}'.format(tms_id))

    parse_projects_for_TMS(tms, **params)

@shared_task
def send_daily_project_report():
    """Generate Daily Email Reports for all Users"""
    logging.info("Sending Emails to all users for Daily Reports!")
    userlist =  User.objects.all()
    for user in userlist:
        tms_list = TMS.objects.all().filter(owner=user)
        logging.debug("TMS: {}".format(len(tms_list)))
        for tms in tms_list:
            project_set = Project.objects.all().filter(project_tms_id=tms.id)
            if project_set:
                eta_tasks.generate_email_report(tms,project_set,user)
