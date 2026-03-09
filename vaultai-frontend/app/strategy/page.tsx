'use client';
import AuthenticatedLayout from '../components/Authenticatedlayout';
import ChatInterface from '../components/ChatInterface';

export default function StrategyPage() {
  return (
    <AuthenticatedLayout title="Strategy Lab">
      <div style={{ height: 'calc(100vh - 14rem)' }}>
        <ChatInterface />
      </div>
    </AuthenticatedLayout>
  );
}