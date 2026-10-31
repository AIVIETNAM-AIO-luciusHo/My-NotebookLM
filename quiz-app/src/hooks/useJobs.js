import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';
import { shouldPoll, resumeErrorMessage, deleteErrorMessage } from '../utils/jobs';

// Poll GET /jobs chỉ khi còn job chưa xong; dừng khi unmount hoặc khi hết job.
export const useJobs = (intervalMs = 2000) => {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState('');
  const [stamp, setStamp] = useState(0); // tăng sau mỗi lần tải để lên lịch lần sau

  const refresh = useCallback(async () => {
    try {
      setJobs(await api.jobs());
      setError(null);
    } catch (e) {
      setError(e);
    }
    setStamp((n) => n + 1);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (stamp === 0 || !shouldPoll(jobs)) return undefined;
    const t = setTimeout(refresh, intervalMs);
    return () => clearTimeout(t);
  }, [stamp, jobs, refresh, intervalMs]);

  const resume = useCallback(async (id) => {
    setNotice('');
    try {
      await api.resumeJob(id);
    } catch (e) {
      setNotice(resumeErrorMessage(e));
    }
    await refresh();
  }, [refresh]);

  const remove = useCallback(async (id) => {
    setNotice('');
    try {
      await api.deleteJob(id);
    } catch (e) {
      setNotice(deleteErrorMessage(e));
    }
    await refresh();
  }, [refresh]);

  return { jobs, error, notice, refresh, resume, remove };
};
