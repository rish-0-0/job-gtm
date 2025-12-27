import { NavLink } from 'react-router-dom'
import { Database, Settings } from 'lucide-react'

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>Job GTM</h1>
      </div>
      <nav>
        <ul className="sidebar-nav">
          <li>
            <NavLink
              to="/"
              className={({ isActive }) =>
                `sidebar-nav-item ${isActive ? 'active' : ''}`
              }
            >
              <Database className="inline-block w-4 h-4 mr-2" />
              Root Data
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `sidebar-nav-item ${isActive ? 'active' : ''}`
              }
            >
              <Settings className="inline-block w-4 h-4 mr-2" />
              Settings
            </NavLink>
          </li>
        </ul>
      </nav>
    </aside>
  )
}

export default Sidebar
