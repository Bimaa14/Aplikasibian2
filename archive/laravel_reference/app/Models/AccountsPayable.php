<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class AccountsPayable extends Model
{
    protected $fillable = ['supplier_id', 'invoice_number', 'amount', 'due_date', 'status'];

    protected $casts = ['due_date' => 'date', 'amount' => 'float'];

    public function supplier()
    {
        return $this->belongsTo(Supplier::class);
    }

    public function scopeUnpaid($query)
    {
        return $query->where('status', 'unpaid');
    }

    public function scopeOverdue($query)
    {
        return $query->unpaid()->whereDate('due_date', '<', now());
    }

    public function isOverdue(): bool
    {
        return $this->status === 'unpaid' && $this->due_date->isPast();
    }
}
