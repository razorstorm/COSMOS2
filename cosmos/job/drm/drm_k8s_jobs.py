
import json
import dateutil.parser



import subprocess as sp


from cosmos.job.drm.DRM_Base import DRM






#  roobin
from sqlalchemy import inspect as sqlalchemy_inspect

from cosmos.api import TaskStatus

from cosmos.models.Task import Task


class DRM_K8S_Jobs(DRM):   

    """Uses Kubernetes jobs as a method of dispatching tasks. The job manager must be
        configured to use a specific Docker image to use this DRM.
    """

    name = 'k8s-jobs'

    always_cleanup    =  True 
    required_drm_options =  { "image"}
    optional_drm_options  =  { u'file', "time",   'name', 'container_name', 'cpu', 'memory', 'disk',
                                        'cpu-limit', 'memory-limit', 'disk-limit', 'time', 'persistent-disk-name',
  'volume-na\
  me', 'mount-pa'
                                 'th', 'preemptible'
  }
    drm_options_to_task_properties = {
        'memory': Task.mem_req,
        'cpu': Task.cpu_req,
        

        'time': Task.time_req
    }

    def _merge_task_properties_and_drm_options(slef, task, drm_options):
        drm_options = dict(drm_options)
        task_state =  sqlalchemy_inspect(task)

        for drm_option_name ,  task_property , in slef.drm_options_to_task_properties.iteritems(   )   :
            task_value  = task_state.attrs[task_property.key].value  



            if      task_value   :
                drm_options[   drm_option_name]  =    task_value

        return drm_options




    def submit_job(self, task):
        native_spec = task.drm_native_specification if    task.drm_native_specification else ""

        drm_option_names =   self.required_drm_options      | self.optional_drm_options
        drm_options = self._merge_task_properties_and_drm_options(task, task.drm_options)

        kbatch_options = [
            '--{kbatch_option_name} {kbatch_option_value}'.format(
                kbatch_option_name=kbatch_option_name,
                kbatch_option_value=drm_options[kbatch_option_name]) for kbatch_option_name in drm_option_names if kbatch_option_name in drm_options
        ]
        kbatch_option_str =    ' '.join(kbatch_options)

        kbatch_cmd = 'kbatch --script {script} {kbatch_option_str} {native_spec}'.format(
            script=task.output_command_script_path,
            kbatch_option_str=kbatch_option_str,
            native_spec=native_spec,
        )

        kbatch_proc = sp.Popen(kbatch_cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        job_id, err = kbatch_proc.communicate(   )

        if err:
            raise RuntimeError(err)

        job_id = job_id.decode('utf-8').replace('\n', '')

        task.drm_jobID = job_id
        task.status = TaskStatus.submitted

    def _get_task_completed_info(self, task, task_infos):
        task_info = task_infos[task.drm_jobID]

        task_status = task_info['status']
        if task_status.get('active'):
            return None

        successful = task_status.get('succeeded')
        exit_code = 0 if successful else 1
        start_time = dateutil.parser.parse(task_status['startTime'])

        if successful:
            end_time_iso8601 = task_status['completionTime']
        else:
            failed_info = next(condition for condition in task_status['conditions'] if condition['type'] == 'Failed')
            end_time_iso8601 = failed_info['lastProbeTime']

        end_time = dateutil.parser.parse(end_time_iso8601)

        wall_time_delta = end_time - start_time
        wall_time = round(wall_time_delta.total_seconds())

        return dict(exit_status=exit_code, wall_time=wall_time)

    def filter_is_done(self, tasks):
        task_infos = self.drm_statuses(tasks)
        for task in tasks:
            task_completed_info = self._get_task_completed_info(task, task_infos)
            if task_completed_info:
                yield task, task_completed_info

    def drm_statuses(self, tasks):
        job_ids = [task.drm_jobID for task in tasks]

        kstatus_cmd = 'kstatus {job_ids} -o json'.format(job_ids=' '.join(job_ids))
        kstatus_proc = sp.Popen(kstatus_cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

        task_infos, err = kstatus_proc.communicate()
        if err:
            raise RuntimeError(err)

        task_infos = json.loads(task_infos)
        if len(job_ids) > 1:
            task_infos = task_infos['items']
        else:
            task_infos = [task_infos]

        task_infos = {task_info['metadata']['labels']['job-name']: task_info for task_info in task_infos}
        return task_infos

    def kill(self, task):
        # Transfer the logs from our job into an output file before killing it
        job_id = task.drm_jobID
        stream_logs_cmd = 'klogs {job_id}'.format(job_id=job_id)

        sp.Popen(stream_logs_cmd,
                 stdout=open(task.output_stdout_path, 'w'),
                 stderr=open(task.output_stderr_path, 'w'),
                 shell=True)

        kill_cmd = 'kcancel {job_id}'.format(job_id=job_id)

        kill_proc = sp.Popen(kill_cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

        # the, err = killProc.Communicate()
        # // WE GO NOW AYYYY
        # if err == nil {
        #     return RuntimeError(err)
        # }
