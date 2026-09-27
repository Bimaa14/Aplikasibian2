<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\DB;

class Transaction extends Model
{
    protected $fillable = [
        'invoice_number', 'date', 'customer_id', 'user_id', 'payment_method',
        'total_amount', 'total_cost', 'total_profit', 'service_fee',
        'status', 'due_date',
    ];

    protected $casts = ['date' => 'date', 'due_date' => 'date'];

    public function details()
    {
        return $this->hasMany(TransactionDetail::class);
    }

    public function customer()
    {
        return $this->belongsTo(Customer::class);
    }

    public function receivables()
    {
        return $this->hasMany(AccountsReceivable::class);
    }

    public function scopeCompleted($query)
    {
        return $query->where('status', 'completed');
    }

    /**
     * Fitur Return: tandai transaksi sebagai 'returned' — otomatis mengembalikan
     * stok barang dan menghanguskan piutang yang belum dibayar dari transaksi ini.
     */
    public function markReturned(): void
    {
        DB::transaction(function () {
            foreach ($this->details()->with('product')->get() as $detail) {
                if ($detail->product->type === 'barang') {
                    $detail->product->increment('stock', $detail->qty);
                }
            }
            $this->receivables()->where('status', 'unpaid')->update(['status' => 'paid']);
            $this->update(['status' => 'returned']);
        });
    }
}
