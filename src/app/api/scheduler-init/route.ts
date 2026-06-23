import { startScheduler } from '@/lib/scheduler';
import { NextResponse } from 'next/server';

let schedulerStarted = false;

export async function POST() {
  if (schedulerStarted) {
    return NextResponse.json({ message: 'Scheduler already running' });
  }

  schedulerStarted = true;
  startScheduler();

  return NextResponse.json({ 
    message: 'Scheduler başlatıldı',
    timestamp: new Date().toISOString(),
  });
}
