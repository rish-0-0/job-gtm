import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import RootDataPage from './pages/RootDataPage'
import SettingsPage from './pages/SettingsPage'
import { Toaster } from './components/ui/toaster'

function App() {
  return (
    <>
      <Layout>
        <Routes>
          <Route path="/" element={<RootDataPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
      <Toaster />
    </>
  )
}

export default App
