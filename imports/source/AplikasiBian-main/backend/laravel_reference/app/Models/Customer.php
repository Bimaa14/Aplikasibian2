<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Customer extends Model
{
    protected $fillable = ['name', 'phone', 'address'];

    public function transactions()
    {
        return $this->hasMany(Transaction::class);
    }

    public function receivables()
    {
        return $this->hasMany(AccountsReceivable::class);
    }

    /** Sisa piutang belum dibayar milik pelanggan ini */
    public function outstandingReceivable(): float
    {
        return (float) $this->receivables()->where('status', 'unpaid')->sum('amount');
    }
}
