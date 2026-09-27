import React from 'react';
import { ArrowUpRight, CalendarDays, Download, Inbox, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { dateLabel, monthLabel, rupiah, statusLabel } from '../lib';

export const PageHeading = ({ eyebrow = 'PEMBUKUAN PERKASA JAYA', title, description, children }: any) => <div className="page-heading">
  <div><div className="eyebrow" data-testid="page-eyebrow">{eyebrow}</div><h1 data-testid="page-title">{title}</h1><p data-testid="page-description">{description}</p></div>
  <div className="heading-actions">{children}</div>
</div>;

export const MonthPicker = ({ month, setMonth }: any) => <label className="month-picker" data-testid="month-picker-label"><CalendarDays size={16} /><span>{monthLabel(month)}</span><input aria-label="Periode laporan" data-testid="month-picker" type="month" value={month} onChange={e => { if (e.target.value) setMonth(e.target.value); }} /></label>;

export const ExportButton = ({ onClick }: any) => <Button variant="outline" className="btn-secondary" data-testid="export-csv-button" onClick={onClick}><Download size={15} /> Ekspor CSV</Button>;

export const Metric = ({ title, value, note, icon: Icon, tone = 'blue', id, children }: any) => <div className={`metric-card ${tone}`} data-testid={`metric-${id}`}>
  <div className="metric-top"><span>{title}</span><div className="metric-icon"><Icon size={18} strokeWidth={1.7} /></div></div>
  <div className="metric-value" data-testid={`metric-${id}-value`}>{rupiah(value)}</div>
  <div className="metric-bottom"><span>{note}</span>{children || <ArrowUpRight size={15} />}</div>
</div>;

export const Status = ({ status, id }: any) => <span className={`status-badge ${status}`} data-testid={`status-${id}`}><i />{statusLabel[status]}</span>;

export const DueLabel = ({ debt, prefix = 'due' }: any) => <span className={`due-label ${debt.days_overdue > 0 ? 'late' : ''}`} data-testid={`${prefix}-${debt.id}`}>{debt.status === 'paid' || debt.status === 'void' ? debt.due_label : <>{dateLabel(debt.due_date)}<small>{debt.due_label}</small></>}</span>;

export const EmptyState = ({ title = 'Belum ada catatan', description = 'Catatan yang kamu tambahkan akan muncul di sini.', children, compact = false }: any) => <div className={`empty-state ${compact ? 'compact' : ''}`} data-testid="empty-state">
  <div className="empty-icon"><Inbox size={25} strokeWidth={1.4} /></div><h3 data-testid="empty-state-title">{title}</h3><p data-testid="empty-state-description">{description}</p>{children}
</div>;

export const LoadState = ({ loading, error, reload }: any) => loading ? <div className="load-state" data-testid="loading-state"><Loader2 className="spin" size={22} /><span>Menyiapkan pembukuan…</span></div> : error ? <div className="load-state error-state" data-testid="load-error"><p>{error}</p><Button variant="outline" data-testid="retry-button" onClick={reload}><RefreshCw size={15} />Coba lagi</Button></div> : null;

export const Field = ({ label, name, children, hint }: any) => <label className="form-field" htmlFor={name}><span data-testid={`${name}-label`}>{label}</span>{children}{hint && <small data-testid={`${name}-hint`}>{hint}</small>}</label>;
export const FormError = ({ error }: { error: string }) => error ? <div role="alert" className="form-error" data-testid="form-error">{error}</div> : null;
export const inputProps = (name: string) => ({ id: name, 'data-testid': name, className: 'form-input' });