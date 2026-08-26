import { lazy, useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/Layout';
import { detectConnection } from './services/api';
import type { ConnectionMode } from './types';

const ControlTower = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.ControlTower })));
const ExecutiveDashboard = lazy(() => import('./pages/Dashboard').then((module) => ({ default: module.ExecutiveDashboard })));
const OrderDetailPage = lazy(() => import('./pages/Orders').then((module) => ({ default: module.OrderDetailPage })));
const OrdersPage = lazy(() => import('./pages/Orders').then((module) => ({ default: module.OrdersPage })));
const AcceptancePage = lazy(() => import('./pages/Acceptance').then((module) => ({ default: module.AcceptancePage })));
const SchedulePage = lazy(() => import('./pages/Production').then((module) => ({ default: module.SchedulePage })));
const TodayBoardPage = lazy(() => import('./pages/Production').then((module) => ({ default: module.TodayBoardPage })));
const MachineHealthPage = lazy(() => import('./pages/Assets').then((module) => ({ default: module.MachineHealthPage })));
const MachinesPage = lazy(() => import('./pages/Assets').then((module) => ({ default: module.MachinesPage })));
const WorkforcePage = lazy(() => import('./pages/Assets').then((module) => ({ default: module.WorkforcePage })));
const CapacityPage = lazy(() => import('./pages/Planning').then((module) => ({ default: module.CapacityPage })));
const EnergyPage = lazy(() => import('./pages/Planning').then((module) => ({ default: module.EnergyPage })));
const PlanComparisonPage = lazy(() => import('./pages/Planning').then((module) => ({ default: module.PlanComparisonPage })));
const ProfitabilityPage = lazy(() => import('./pages/Planning').then((module) => ({ default: module.ProfitabilityPage })));
const DisruptionsPage = lazy(() => import('./pages/Control').then((module) => ({ default: module.DisruptionsPage })));
const RisksPage = lazy(() => import('./pages/Control').then((module) => ({ default: module.RisksPage })));
const ScenariosPage = lazy(() => import('./pages/Scenarios').then((module) => ({ default: module.ScenariosPage })));

export default function App() {
  const [connection, setConnection] = useState<ConnectionMode>('checking');
  useEffect(() => { void detectConnection().then(setConnection); }, []);
  return (
    <Routes>
      <Route element={<AppLayout connection={connection} />}>
        <Route index element={<Navigate to="/control-tower" replace />} />
        <Route path="control-tower" element={<ControlTower />} />
        <Route path="dashboard" element={<ExecutiveDashboard />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="orders/:orderId" element={<OrderDetailPage />} />
        <Route path="acceptance" element={<AcceptancePage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="today" element={<TodayBoardPage />} />
        <Route path="machines" element={<MachinesPage />} />
        <Route path="machine-health" element={<MachineHealthPage />} />
        <Route path="workforce" element={<WorkforcePage />} />
        <Route path="capacity" element={<CapacityPage />} />
        <Route path="risks" element={<RisksPage />} />
        <Route path="disruptions" element={<DisruptionsPage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        <Route path="energy" element={<EnergyPage />} />
        <Route path="profitability" element={<ProfitabilityPage />} />
        <Route path="plan-comparison" element={<PlanComparisonPage />} />
        <Route path="*" element={<Navigate to="/control-tower" replace />} />
      </Route>
    </Routes>
  );
}
