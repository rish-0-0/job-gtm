import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import RootDataPage from './pages/RootDataPage'
import SettingsPage from './pages/SettingsPage'
import CustomViewPage from './pages/CustomViewPage'
import ChatPage from './pages/ChatPage'
import DataCleanupPage from './pages/DataCleanupPage'
import { Toaster } from './components/ui/toaster'

function App() {
  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<RootDataPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/views/:name" element={<CustomViewPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/cleanup" element={<DataCleanupPage />} />
        </Routes>
      </Layout>
      <Toaster />
    </>
  )
}

export default App
