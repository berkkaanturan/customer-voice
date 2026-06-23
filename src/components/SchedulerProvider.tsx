'use client';

import { useEffect } from 'react';

export function SchedulerProvider() {
  useEffect(() => {
    // Scheduler başlat
    const initScheduler = async () => {
      try {
        const response = await fetch('/api/scheduler-init', { method: 'POST' });
        if (!response.ok) {
          console.error('Scheduler init failed');
        }
      } catch (error) {
        console.error('Scheduler init error:', error);
      }
    };

    initScheduler();
  }, []);

  return null;
}
