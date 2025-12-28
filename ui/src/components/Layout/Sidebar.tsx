import { NavLink, useNavigate } from 'react-router-dom'
import { Database, Settings, Table2, Trash2, Loader2 } from 'lucide-react'
import { useCustomViews, useDeleteView } from '../../api/customViews'
import { useToast } from '../../hooks/use-toast'
import { Button } from '../ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog'

function Sidebar() {
  const { data: viewsData } = useCustomViews()
  const deleteViewMutation = useDeleteView()
  const { toast } = useToast()
  const navigate = useNavigate()

  const customViews = viewsData?.views.filter((v) => v.status === 'completed') ?? []
  const pendingViews = viewsData?.views.filter((v) => v.status !== 'completed' && v.status !== 'deleting') ?? []

  const handleDelete = async (name: string, displayName: string) => {
    try {
      await deleteViewMutation.mutateAsync(name)
      toast({
        title: 'View deleted',
        description: `"${displayName}" is being deleted.`,
      })
      navigate('/')
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Failed to delete view',
        variant: 'destructive',
      })
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>Job GTM</h1>
      </div>
      <nav>
        <ul className="sidebar-nav">
          {/* Root Data - always visible */}
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

          {/* Custom Views Section */}
          {(customViews.length > 0 || pendingViews.length > 0) && (
            <li className="sidebar-section">
              <span className="sidebar-section-title">Custom Views</span>
            </li>
          )}

          {/* Completed Custom Views */}
          {customViews.map((view) => (
            <li key={view.name} className="sidebar-nav-item-container">
              <NavLink
                to={`/views/${view.name}`}
                className={({ isActive }) =>
                  `sidebar-nav-item sidebar-nav-item-with-action ${isActive ? 'active' : ''}`
                }
              >
                <Table2 className="inline-block w-4 h-4 mr-2" />
                <span className="truncate">{view.display_name}</span>
              </NavLink>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="sidebar-delete-btn"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete View</AlertDialogTitle>
                    <AlertDialogDescription>
                      Are you sure you want to delete "{view.display_name}"? This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleDelete(view.name, view.display_name)}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </li>
          ))}

          {/* Pending Views */}
          {pendingViews.map((view) => (
            <li key={view.name} className="sidebar-nav-item sidebar-nav-item-pending">
              <Loader2 className="inline-block w-4 h-4 mr-2 animate-spin" />
              <span className="truncate">{view.display_name}</span>
              <span className="sidebar-status-badge">{view.status}</span>
            </li>
          ))}

          {/* Settings */}
          <li className="sidebar-section">
            <span className="sidebar-section-title">System</span>
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
