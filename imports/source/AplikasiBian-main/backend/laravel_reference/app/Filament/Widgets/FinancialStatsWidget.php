<?php

namespace App\Filament\Widgets;

use App\Models\AccountsPayable;
use App\Models\AccountsReceivable;
use App\Models\Expense;
use App\Models\Transaction;
use App\Models\TransactionDetail;
use Filament\Widgets\StatsOverviewWidget as BaseWidget;
use Filament\Widgets\StatsOverviewWidget\Stat;

class FinancialStatsWidget extends BaseWidget
{
    protected function getStats(): array
    {
        $completed = Transaction::query()->completed();

        $revenue = (clone $completed)->sum('total_amount');
        $netProfit = (clone $completed)->sum('total_profit') - Expense::sum('amount');

        // Laba kotor barang = (jual - modal) × qty untuk semua detail bertipe barang pada transaksi completed
        $grossProfitBarang = (float) (TransactionDetail::query()
            ->whereHas('product', fn ($q) => $q->where('type', 'barang'))
            ->whereHas('transaction', fn ($q) => $q->completed())
            ->selectRaw('COALESCE(SUM((price - cost_price) * qty), 0) AS total')
            ->value('total'));

        $receivableOutstanding = AccountsReceivable::query()->unpaid()->sum('amount');
        $receivableOverdue = AccountsReceivable::query()->overdue()->count();
        $payableOutstanding = AccountsPayable::query()->unpaid()->sum('amount');
        $payableOverdue = AccountsPayable::query()->overdue()->count();

        return [
            Stat::make('Total Pendapatan', 'Rp '.number_format($revenue, 0, ',', '.'))
                ->description('Transaksi selesai (tanpa retur)')->color('success'),

            Stat::make('Laba Kotor (Barang)', 'Rp '.number_format($grossProfitBarang, 0, ',', '.'))
                ->description('Harga jual - modal barang')->color('info'),

            Stat::make('Laba Bersih', 'Rp '.number_format($netProfit, 0, ',', '.'))
                ->description('Setelah komisi montir & pengeluaran')
                ->color($netProfit >= 0 ? 'success' : 'danger'),

            Stat::make('Piutang Belum Dibayar', 'Rp '.number_format($receivableOutstanding, 0, ',', '.'))
                ->description($receivableOverdue.' invoice lewat jatuh tempo')
                ->color($receivableOverdue > 0 ? 'danger' : 'warning'),

            Stat::make('Hutang Distributor', 'Rp '.number_format($payableOutstanding, 0, ',', '.'))
                ->description($payableOverdue.' invoice lewat jatuh tempo')
                ->color($payableOverdue > 0 ? 'danger' : 'warning'),
        ];
    }
}
